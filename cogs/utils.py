import os
import ast
import importlib.util
from typing import List


class BlacklistManager:
    """Shared manager for loading/saving/reloading the blacklist from words.py."""
    
    def __init__(self, words_file: str = 'cogs/words.py'):
        self.words_file = words_file
        self.blacklist: List[str] = []
        self.blacklist = self.load()

    def load(self) -> List[str]:
        """Load blacklist from words.py Python file if it exists."""
        if not os.path.exists(self.words_file):
            self.blacklist = []
            return self.blacklist

        try:
            with open(self.words_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Try AST parsing first
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name) and target.id == 'blat':
                                if isinstance(node.value, ast.List):
                                    words = []
                                    for elem in node.value.elts:
                                        if isinstance(elem, ast.Constant) and isinstance(elem.value, str):
                                            words.append(elem.value)
                                    self.blacklist = words
                                    return self.blacklist
            except (SyntaxError, ValueError):
                pass
            
            # Fallback: Dynamic import
            spec = importlib.util.spec_from_file_location("words_module", self.words_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                if hasattr(module, 'blat') and isinstance(module.blat, list):
                    self.blacklist = module.blat
                    return self.blacklist
                    
        except Exception as e:
            print(f"Error loading blacklist: {e}")
        
        self.blacklist = []
        return self.blacklist

    def save(self) -> bool:
        """Save blacklist to words.py by regenerating the file content."""
        try:
            content = f"blat = {self.blacklist!r}\n"
            with open(self.words_file, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except IOError as e:
            print(f"Error saving blacklist: {e}")
            return False

    def reload(self) -> List[str]:
        """Reload the blacklist from words.py."""
        self.blacklist = self.load()
        return self.blacklist

    def add(self, word: str) -> bool:
        """Add a word to the blacklist. Returns True if added."""
        if not isinstance(word, str):
            return False
            
        word_lower = word.lower().strip()
        if not word_lower or word_lower in self.blacklist:
            return False
        
        self.blacklist.append(word_lower)
        return self.save()

    def remove(self, word: str) -> bool:
        """Remove a word from the blacklist. Returns True if removed."""
        if not isinstance(word, str):
            return False
            
        word_lower = word.lower().strip()
        if not word_lower or word_lower not in self.blacklist:
            return False
        
        try:
            self.blacklist.remove(word_lower)
            return self.save()
        except ValueError:
            return False

    def contains(self, word: str) -> bool:
        """Check if a word is in the blacklist."""
        if not isinstance(word, str):
            return False
        return word.lower().strip() in self.blacklist

    def __contains__(self, word: str) -> bool:
        """Support 'word in manager' syntax."""
        return self.contains(word)

    def __len__(self) -> int:
        """Get number of blacklisted words."""
        return len(self.blacklist)

    @property
    def current(self) -> List[str]:
        """Get the current blacklist as a list."""
        return self.blacklist.copy()

    def clear(self) -> bool:
        """Clear all words from blacklist."""
        self.blacklist = []
        return self.save()