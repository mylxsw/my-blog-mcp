import os
import re
import json
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
        from datetime import datetime
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
        if not git_repo.write_file(filepath, final_content, f"Create new article: {title} @deploy"):
            return f"Error: Failed to create article file {filepath}"
        
        return f"Successfully created article '{title}' at {filepath}"
        
    except Exception as e:
        return f"Error creating article: {str(e)}"    


if __name__ == "__main__":
    mcp.run(transport=os.getenv("BLOG_MCP_TRANSPORT", "http"), host="0.0.0.0", port=8000)
