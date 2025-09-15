import os
import re
import json
from datetime import datetime
from typing import Annotated, Optional
from fastmcp import FastMCP
from fastmcp.server.auth import StaticTokenVerifier
from git import GitRepository
from pypinyin import lazy_pinyin, Style

mcp = FastMCP("Blog MCP Server")

# Authentication setup
auth_token = os.getenv("BLOG_MCP_AUTH_TOKEN")
if auth_token is not None:
    mcp.auth = StaticTokenVerifier(
        tokens={
            auth_token: {
                "client_id": "default",
                "scopes": ["read:repo", "write:repo", "admin:repo"]
            }
        },
        required_scopes=["read:repo", "write:repo"],
    )

# Environment variables for GitHub configuration
github_repo_url = os.getenv("GITHUB_REPO_URL")
if github_repo_url is None:
    raise ValueError("GITHUB_REPO_URL is not set (e.g., 'username/repository' or full URL)")

github_api_token = os.getenv("GITHUB_API_TOKEN")
if github_api_token is None:
    raise ValueError("GITHUB_API_TOKEN is not set")

# Initialize GitRepository instance
try:
    git_repo = GitRepository(github_repo_url, github_api_token)
except Exception as e:
    raise ValueError(f"Failed to initialize GitRepository: {e}")


def title_to_filename(title: str) -> str:
    """Convert title to valid filename with pinyin for Chinese characters"""
    # Convert Chinese characters to pinyin
    pinyin_list = lazy_pinyin(title, style=Style.NORMAL)
    filename = ''.join(pinyin_list)
    
    # Replace spaces and special characters with hyphens
    filename = re.sub(r'[^\w\-]', '-', filename)
    
    # Remove multiple consecutive hyphens
    filename = re.sub(r'-+', '-', filename)
    
    # Remove leading and trailing hyphens
    filename = filename.strip('-')
    
    # Convert to lowercase
    filename = filename.lower()
    
    return filename

def has_markdown_title(content: str) -> bool:
    """Check if content has a markdown title (first non-empty line starts with #)"""
    content = content.strip()
    if not content:
        return False
    
    first_line = content.split('\n')[0]
    return first_line.startswith('# ')

def add_title_to_content(title: str, content: str) -> str:
    """Add title as markdown header if content doesn't have one"""
    if has_markdown_title(content):
        return content
    else:
        return f"# {title}\n\n{content}"

@mcp.tool
def create_new_article(
    title: Annotated[str, "Title of the new article"],
    content: Annotated[str, "Content of the new article, should be in Markdown format"],
    category: Annotated[Optional[str], "Category of the new article, should be one of the following: web3, note, default is note"] = "note",
) -> str:
    """Create a new article with Markdown format"""
    
    if category not in ["web3", "note"]:
        return "Error: Category should be one of the following: web3, note"
    
    try:
        # 1. Convert title to filename
        filename = title_to_filename(title)
        filepath = f"pages/{category}/{filename}.md"
        
        # 2. Check and add title to content if needed
        final_content = add_title_to_content(title, content)
        
        # Add AI creation timestamp at the end
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ai_footer = f"\n\n---\n> This article was created by AI at {current_time} and is for reference only."
        final_content += ai_footer
        
        # 3. Read and update _meta.json
        meta_filepath = f"pages/{category}/_meta.json"
        meta_content = git_repo.read_file(meta_filepath)
        
        if meta_content is None:
            # Create new _meta.json if it doesn't exist
            meta_data = {filename: title}
        else:
            # Parse existing _meta.json
            try:
                meta_data = json.loads(meta_content)
            except json.JSONDecodeError:
                # If JSON is invalid, create new structure
                meta_data = {}
            
            # Add new article to meta data
            meta_data[filename] = title
        
        # Write updated _meta.json
        updated_meta_content = json.dumps(meta_data, ensure_ascii=False, indent=4)
        if not git_repo.write_file(meta_filepath, updated_meta_content, f"Add article '{title}' to _meta.json"):
            return f"Error: Failed to update _meta.json"
        
        # 4. Create the article file
        if not git_repo.write_file(filepath, final_content, f"Create new article: {title}"):
            return f"Error: Failed to create article file {filepath}"
        
        return f"Successfully created article '{title}' at {filepath}"
        
    except Exception as e:
        return f"Error creating article: {str(e)}"    


@mcp.tool
def update_article(
    path: Annotated[str, "Path to the article file (e.g., 'pages/note/article-name.md')"],
    new_content: Annotated[str, "New content for the article in Markdown format"],
    title: Annotated[Optional[str], "New title for the article. If provided, will update the title in _meta.json"] = None,
) -> str:
    """Update an existing article with new content and optionally update the title"""
    
    try:
        # Check if the file exists
        existing_content = git_repo.read_file(path)
        if existing_content is None:
            return f"Error: Article not found at path '{path}'"
        
        # Extract category and filename from path
        path_parts = path.split('/')
        if len(path_parts) < 3 or not path_parts[0] == 'pages':
            return f"Error: Invalid article path format. Expected 'pages/category/filename.md'"
        
        category = path_parts[1]
        filename = path_parts[2].replace('.md', '')
        
        # Update _meta.json if title is provided
        if title is not None:
            meta_filepath = f"pages/{category}/_meta.json"
            meta_content = git_repo.read_file(meta_filepath)
            
            if meta_content is not None:
                try:
                    meta_data = json.loads(meta_content)
                    if filename in meta_data:
                        meta_data[filename] = title
                        
                        # Write updated _meta.json
                        updated_meta_content = json.dumps(meta_data, ensure_ascii=False, indent=4)
                        if not git_repo.write_file(meta_filepath, updated_meta_content, f"Update article title '{filename}' in _meta.json"):
                            return f"Error: Failed to update _meta.json"
                except json.JSONDecodeError:
                    return f"Error: Invalid _meta.json format"
            else:
                return f"Error: _meta.json not found for category '{category}'"
        
        # Update the article file
        if not git_repo.write_file(path, new_content, f"Update article: {path}"):
            return f"Error: Failed to update article at {path}"
        
        success_msg = f"Successfully updated article at {path}"
        if title is not None:
            success_msg += f" with new title '{title}'"
        
        return success_msg
        
    except Exception as e:
        return f"Error updating article: {str(e)}"


@mcp.tool
def get_article(
    path: Annotated[str, "Path to the article file (e.g., 'pages/note/article-name.md')"],
) -> str:
    """Get the content of an existing article"""
    
    try:
        content = git_repo.read_file(path)
        if content is None:
            return f"Error: Article not found at path '{path}'"
        
        return content
        
    except Exception as e:
        return f"Error reading article: {str(e)}"


@mcp.tool
def delete_article(
    path: Annotated[str, "Path to the article file (e.g., 'pages/note/article-name.md')"],
) -> str:
    """Delete an existing article and update _meta.json"""
    
    try:
        # Check if the file exists
        existing_content = git_repo.read_file(path)
        if existing_content is None:
            return f"Error: Article not found at path '{path}'"
        
        # Extract category and filename from path
        path_parts = path.split('/')
        if len(path_parts) < 3 or not path_parts[0] == 'pages':
            return f"Error: Invalid article path format. Expected 'pages/category/filename.md'"
        
        category = path_parts[1]
        filename = path_parts[2].replace('.md', '')
        
        # Update _meta.json to remove the article
        meta_filepath = f"pages/{category}/_meta.json"
        meta_content = git_repo.read_file(meta_filepath)
        
        if meta_content is not None:
            try:
                meta_data = json.loads(meta_content)
                if filename in meta_data:
                    del meta_data[filename]
                    
                    # Write updated _meta.json
                    updated_meta_content = json.dumps(meta_data, ensure_ascii=False, indent=4)
                    if not git_repo.write_file(meta_filepath, updated_meta_content, f"Remove article '{filename}' from _meta.json"):
                        return f"Error: Failed to update _meta.json"
            except json.JSONDecodeError:
                # If JSON is invalid, continue with deletion
                pass
        
        # Delete the article file
        if not git_repo.delete_file(path, f"Delete article: {path}"):
            return f"Error: Failed to delete article at {path}"
        
        return f"Successfully deleted article at {path}"
        
    except Exception as e:
        return f"Error deleting article: {str(e)}"


@mcp.tool
def get_article_list(
    category: Annotated[Optional[str], "Category to filter articles (web3, note). If not provided, returns all categories"] = None,
) -> str:
    """Get list of articles with their paths and titles"""
    
    try:
        result = {}
        
        if category is not None:
            if category not in ["web3", "note"]:
                return "Error: Category should be one of the following: web3, note"
            
            # Get articles for specific category
            meta_filepath = f"pages/{category}/_meta.json"
            meta_content = git_repo.read_file(meta_filepath)
            
            if meta_content is not None:
                try:
                    meta_data = json.loads(meta_content)
                    for filename, title in meta_data.items():
                        result[f"pages/{category}/{filename}.md"] = title
                except json.JSONDecodeError:
                    pass
        else:
            # Get articles for all categories
            for cat in ["web3", "note"]:
                meta_filepath = f"pages/{cat}/_meta.json"
                meta_content = git_repo.read_file(meta_filepath)
                
                if meta_content is not None:
                    try:
                        meta_data = json.loads(meta_content)
                        for filename, title in meta_data.items():
                            result[f"pages/{cat}/{filename}.md"] = title
                    except json.JSONDecodeError:
                        pass
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return f"Error getting article list: {str(e)}"


@mcp.tool
def deploy() -> str:
    """Create a deployment commit with @deploy comment to trigger deployment"""
    
    try:
        # Create/update .deploy-version file with current timestamp
        deploy_filepath = ".deploy-version"
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        deploy_content = f"deploy-version: {current_timestamp}"
        
        # Create or update the .deploy-version file
        if not git_repo.write_file(deploy_filepath, deploy_content, "@deploy"):
            return "Error: Failed to create/update .deploy-version file"
        
        return f"Successfully created deployment commit with @deploy (version: {current_timestamp})"
        
    except Exception as e:
        return f"Error creating deployment commit: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport=os.getenv("BLOG_MCP_TRANSPORT", "http"), host="0.0.0.0", port=8000)
