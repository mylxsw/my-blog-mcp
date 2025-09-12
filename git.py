from github import Github
from github.GithubException import GithubException
from typing import Optional


class GitRepository:
    """
    A class to manage GitHub repository operations including file writing, 
    committing, pushing, and force syncing with local repository.
    """
    
    def __init__(self, url: str, api_token: str, default_branch: str = None):
        """
        Initialize the GitRepository with GitHub URL and API token.
        
        Args:
            url (str): GitHub repository URL (e.g., "username/repository" or full URL)
            api_token (str): GitHub personal access token
            default_branch (str): Default branch to use for operations (if None, uses repo default)
        """
        self.api_token = api_token
        self.github = Github(api_token)
        
        # Extract repository name from URL
        if url.startswith(('http://', 'https://')):
            # Extract from full URL
            url_parts = url.rstrip('/').split('/')
            self.repo_name = f"{url_parts[-2]}/{url_parts[-1]}"
        else:
            # Assume it's already in "username/repository" format
            self.repo_name = url
            
        try:
            self.repo = self.github.get_repo(self.repo_name)
            self.default_branch = default_branch or self.repo.default_branch
        except GithubException as e:
            raise ValueError(f"Failed to access repository {self.repo_name}: {e}")
    
    def write_file(self, filepath: str, content: str, commit_message: Optional[str] = None, branch: Optional[str] = None) -> bool:
        """
        Write content to a file in the GitHub repository.
        
        Args:
            filepath (str): Path to the file in the repository
            content (str): Content to write to the file
            commit_message (Optional[str]): Custom commit message. If None, uses default messages.
            branch (Optional[str]): Branch to write to. If None, uses default branch.
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            target_branch = branch or self.default_branch
            
            # Try to get the file first
            try:
                file = self.repo.get_contents(filepath, ref=target_branch)
                # File exists, update it
                update_message = commit_message if commit_message else f"Update {filepath}"
                self.repo.update_file(
                    file.path, 
                    update_message, 
                    content, 
                    file.sha,
                    branch=target_branch
                )
                print(f"Updated {filepath} on branch {target_branch}")
            except GithubException:
                # File doesn't exist, create it
                create_message = commit_message if commit_message else f"Create {filepath}"
                self.repo.create_file(
                    filepath, 
                    create_message, 
                    content,
                    branch=target_branch
                )
                print(f"Created {filepath} on branch {target_branch}")
            
            return True
            
        except GithubException as e:
            print(f"Error writing to {filepath} on branch {target_branch}: {e}")
            return False
    
    def read_file(self, filepath: str, branch: Optional[str] = None) -> Optional[str]:
        """
        Read content from a file in the GitHub repository.
        
        Args:
            filepath (str): Path to the file in the repository
            branch (Optional[str]): Branch to read from. If None, uses default branch.
            
        Returns:
            Optional[str]: File content if successful, None otherwise
        """
        try:
            target_branch = branch or self.default_branch
            file = self.repo.get_contents(filepath, ref=target_branch)
            return file.decoded_content.decode('utf-8')
        except GithubException as e:
            print(f"Error reading {filepath} from branch {target_branch}: {e}")
            return None
    
    def list_files(self, path: str = "", branch: Optional[str] = None) -> list:
        """
        List files in the repository.
        
        Args:
            path (str): Directory path to list (empty string for root)
            branch (Optional[str]): Branch to list files from. If None, uses default branch.
            
        Returns:
            list: List of file paths
        """
        try:
            target_branch = branch or self.default_branch
            contents = self.repo.get_contents(path, ref=target_branch)
            files = []
            
            for content in contents:
                if content.type == "dir":
                    files.extend(self.list_files(content.path, target_branch))
                else:
                    files.append(content.path)
            
            return files
        except GithubException as e:
            print(f"Error listing files from branch {target_branch}: {e}")
            return []
    
    def delete_file(self, filepath: str, commit_message: Optional[str] = None, branch: Optional[str] = None) -> bool:
        """
        Delete a file from the GitHub repository.
        
        Args:
            filepath (str): Path to the file in the repository to delete
            commit_message (Optional[str]): Custom commit message. If None, uses default message.
            branch (Optional[str]): Branch to delete from. If None, uses default branch.
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            target_branch = branch or self.default_branch
            
            # Get the file to delete
            file = self.repo.get_contents(filepath, ref=target_branch)
            
            # Delete the file
            delete_message = commit_message if commit_message else f"Delete {filepath}"
            self.repo.delete_file(
                file.path,
                delete_message,
                file.sha,
                branch=target_branch
            )
            print(f"Deleted {filepath} from branch {target_branch}")
            return True
            
        except GithubException as e:
            print(f"Error deleting {filepath} from branch {target_branch}: {e}")
            return False
    
    def list_branches(self) -> list:
        """
        List all branches in the repository.
        
        Returns:
            list: List of branch names
        """
        try:
            branches = self.repo.get_branches()
            return [branch.name for branch in branches]
        except GithubException as e:
            print(f"Error listing branches: {e}")
            return []
    
    def create_branch(self, branch_name: str, from_branch: Optional[str] = None) -> bool:
        """
        Create a new branch in the repository.
        
        Args:
            branch_name (str): Name of the new branch
            from_branch (Optional[str]): Branch to create from. If None, uses default branch.
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            source_branch = from_branch or self.default_branch
            source_ref = self.repo.get_git_ref(f"heads/{source_branch}")
            self.repo.create_git_ref(f"refs/heads/{branch_name}", source_ref.object.sha)
            print(f"Created branch {branch_name} from {source_branch}")
            return True
        except GithubException as e:
            print(f"Error creating branch {branch_name}: {e}")
            return False
    
    def get_branch_info(self, branch_name: Optional[str] = None) -> Optional[dict]:
        """
        Get information about a specific branch.
        
        Args:
            branch_name (Optional[str]): Name of the branch. If None, uses default branch.
            
        Returns:
            Optional[dict]: Branch information if successful, None otherwise
        """
        try:
            target_branch = branch_name or self.default_branch
            branch = self.repo.get_branch(target_branch)
            return {
                "name": branch.name,
                "commit_sha": branch.commit.sha,
                "commit_message": branch.commit.commit.message,
                "commit_author": branch.commit.commit.author.name,
                "commit_date": branch.commit.commit.author.date.isoformat(),
                "protected": branch.protected,
            }
        except GithubException as e:
            print(f"Error getting branch info for {target_branch}: {e}")
            return None
