"""Robust code block detection for markdown content."""

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple, Optional


class BlockType(Enum):
    """Types of code blocks."""
    FENCED_BACKTICK = "fenced_backtick"  # ```
    FENCED_TILDE = "fenced_tilde"        # ~~~
    INLINE_CODE = "inline_code"          # `code`
    INDENTED_CODE = "indented_code"      # 4 spaces or tab
    HTML_CODE = "html_code"              # <code> or <pre>


@dataclass
class CodeBlock:
    """Represents a code block in the document."""
    block_type: BlockType
    start_pos: int
    end_pos: int
    start_line: int
    end_line: int
    content: str = ""
    language: str = ""  # For fenced blocks


class CodeBlockDetector:
    """Robust code block detector using state machine approach."""
    
    def __init__(self):
        """Initialize the detector."""
        self.blocks: List[CodeBlock] = []
        self.content = ""
        self.lines: List[str] = []
    
    def detect_code_blocks(self, content: str) -> List[CodeBlock]:
        """Detect all code blocks in the content.
        
        Args:
            content: Markdown content to analyze
            
        Returns:
            List of detected code blocks
        """
        self.content = content
        self.lines = content.splitlines(True)  # Keep line endings
        self.blocks = []
        
        # Detect different types of code blocks in order of precedence
        self._detect_fenced_blocks()
        self._detect_html_blocks()
        self._detect_inline_code()
        self._detect_indented_blocks()
        
        # Sort blocks by start position
        self.blocks.sort(key=lambda b: b.start_pos)
        
        return self.blocks
    
    def is_position_in_code_block(self, pos: int) -> bool:
        """Check if a position is inside any code block.
        
        Args:
            pos: Character position in the content
            
        Returns:
            True if position is inside a code block
        """
        for block in self.blocks:
            if block.start_pos <= pos < block.end_pos:
                return True
        return False
    
    def is_range_in_code_block(self, start_pos: int, end_pos: int) -> bool:
        """Check if a range is inside any code block.
        
        Args:
            start_pos: Start position of the range
            end_pos: End position of the range
            
        Returns:
            True if the entire range is inside a code block
        """
        for block in self.blocks:
            if block.start_pos <= start_pos and end_pos <= block.end_pos:
                return True
        return False
    
    def _detect_fenced_blocks(self) -> None:
        """Detect fenced code blocks (``` and ~~~)."""
        current_pos = 0
        i = 0
        
        while i < len(self.lines):
            line = self.lines[i]
            line_start_pos = current_pos
            stripped_line = line.strip()
            
            # Check for fenced block start
            if stripped_line.startswith('```') and len(stripped_line) >= 3:
                block = self._parse_fenced_block(i, current_pos, '```')
                if block:
                    self.blocks.append(block)
                    # Skip to the end of the block
                    i = block.end_line + 1
                    current_pos = block.end_pos
                    continue
            elif stripped_line.startswith('~~~') and len(stripped_line) >= 3:
                block = self._parse_fenced_block(i, current_pos, '~~~')
                if block:
                    self.blocks.append(block)
                    # Skip to the end of the block
                    i = block.end_line + 1
                    current_pos = block.end_pos
                    continue
            
            current_pos += len(line)
            i += 1
    
    def _parse_fenced_block(
        self, 
        start_line_idx: int, 
        start_pos: int, 
        fence_char: str
    ) -> Optional[CodeBlock]:
        """Parse a fenced code block.
        
        Args:
            start_line_idx: Starting line index
            start_pos: Starting character position
            fence_char: Fence character ('```' or '~~~')
            
        Returns:
            CodeBlock if valid block found, None otherwise
        """
        start_line = self.lines[start_line_idx].strip()
        
        # Extract language if present
        language = ""
        if len(start_line) > len(fence_char):
            language = start_line[len(fence_char):].strip()
        
        # Find closing fence
        current_pos = start_pos + len(self.lines[start_line_idx])
        
        for line_idx in range(start_line_idx + 1, len(self.lines)):
            line = self.lines[line_idx]
            stripped_line = line.strip()
            
            # Check for closing fence - must be at least 3 characters of the same fence type
            if stripped_line.startswith(fence_char) and len(stripped_line) >= 3:
                # Check if it's only fence characters (no other content)
                fence_only = True
                for char in stripped_line:
                    if char != fence_char[0]:  # fence_char is either '```' or '~~~'
                        fence_only = False
                        break
                
                if fence_only or stripped_line == fence_char:
                    # Found closing fence
                    end_pos = current_pos + len(line)
                    
                    block_type = (BlockType.FENCED_BACKTICK if fence_char == '```' 
                                 else BlockType.FENCED_TILDE)
                    
                    return CodeBlock(
                        block_type=block_type,
                        start_pos=start_pos,
                        end_pos=end_pos,
                        start_line=start_line_idx,
                        end_line=line_idx,
                        language=language,
                        content=self.content[start_pos:end_pos]
                    )
            
            current_pos += len(line)
        
        # No closing fence found - treat as invalid
        return None
    
    def _detect_html_blocks(self) -> None:
        """Detect HTML code blocks (<code>, <pre>)."""
        # Find all HTML code/pre tags
        html_patterns = [
            (r'<code\b[^>]*>', r'</code>', BlockType.HTML_CODE),
            (r'<pre\b[^>]*>', r'</pre>', BlockType.HTML_CODE),
        ]
        
        for open_pattern, close_pattern, block_type in html_patterns:
            pos = 0
            while True:
                # Find opening tag
                open_match = re.search(open_pattern, self.content[pos:], re.IGNORECASE)
                if not open_match:
                    break
                
                open_start = pos + open_match.start()
                open_end = pos + open_match.end()
                
                # Find closing tag
                close_match = re.search(close_pattern, self.content[open_end:], re.IGNORECASE)
                if not close_match:
                    pos = open_end
                    continue
                
                close_start = open_end + close_match.start()
                close_end = open_end + close_match.end()
                
                # Create block
                start_line = self.content[:open_start].count('\n')
                end_line = self.content[:close_end].count('\n')
                
                block = CodeBlock(
                    block_type=block_type,
                    start_pos=open_start,
                    end_pos=close_end,
                    start_line=start_line,
                    end_line=end_line,
                    content=self.content[open_start:close_end]
                )
                
                self.blocks.append(block)
                pos = close_end
    
    def _detect_inline_code(self) -> None:
        """Detect inline code blocks (`code`)."""
        # Use a more sophisticated approach to handle backticks
        backtick_positions = []
        
        # Find all backtick positions that are not part of fenced blocks
        pos = 0
        while True:
            pos = self.content.find('`', pos)
            if pos == -1:
                break
            
            # Check if this backtick is inside a fenced block
            if not self._is_pos_in_existing_blocks(pos):
                backtick_positions.append(pos)
            
            pos += 1
        
        # Match backticks in pairs
        i = 0
        while i < len(backtick_positions) - 1:
            start_pos = backtick_positions[i]
            
            # Look for matching closing backtick
            for j in range(i + 1, len(backtick_positions)):
                end_pos = backtick_positions[j]
                
                # Check if the content between backticks is valid inline code
                if self._is_valid_inline_code(start_pos, end_pos):
                    start_line = self.content[:start_pos].count('\n')
                    end_line = self.content[:end_pos + 1].count('\n')
                    
                    block = CodeBlock(
                        block_type=BlockType.INLINE_CODE,
                        start_pos=start_pos,
                        end_pos=end_pos + 1,  # Include closing backtick
                        start_line=start_line,
                        end_line=end_line,
                        content=self.content[start_pos:end_pos + 1]
                    )
                    
                    self.blocks.append(block)
                    
                    # Skip the used backticks
                    i = j + 1
                    break
            else:
                # No matching backtick found
                i += 1
    
    def _is_pos_in_existing_blocks(self, pos: int) -> bool:
        """Check if position is in already detected blocks."""
        for block in self.blocks:
            if block.start_pos <= pos < block.end_pos:
                return True
        return False
    
    def _is_valid_inline_code(self, start_pos: int, end_pos: int) -> bool:
        """Check if backtick pair forms valid inline code.
        
        Args:
            start_pos: Position of opening backtick
            end_pos: Position of closing backtick
            
        Returns:
            True if valid inline code
        """
        # Must be on the same line or span only a few lines
        content_between = self.content[start_pos + 1:end_pos]
        
        # Inline code shouldn't span too many lines
        if content_between.count('\n') > 2:
            return False
        
        # Should not contain other backticks (unless escaped)
        if '`' in content_between:
            return False
        
        # Should not be empty or just whitespace
        if not content_between.strip():
            return False
        
        return True
    
    def _detect_indented_blocks(self) -> None:
        """Detect indented code blocks (4 spaces or 1 tab)."""
        current_pos = 0
        i = 0
        
        while i < len(self.lines):
            line = self.lines[i]
            line_start_pos = current_pos
            
            # Check if line is indented and not in existing block
            if (self._is_indented_line(line) and 
                not self._is_pos_in_existing_blocks(line_start_pos)):
                
                # Find the extent of the indented block
                block_start_line = i
                block_start_pos = line_start_pos
                
                # Scan forward to find end of block
                j = i
                block_end_pos = line_start_pos
                
                while j < len(self.lines):
                    current_line = self.lines[j]
                    
                    # Continue if line is indented or blank
                    if (self._is_indented_line(current_line) or 
                        current_line.strip() == ""):
                        block_end_pos += len(current_line)
                        j += 1
                    else:
                        break
                
                # Create block if it's substantial
                if j > i + 1 or len(line.strip()) > 0:  # More than one line or non-empty
                    block = CodeBlock(
                        block_type=BlockType.INDENTED_CODE,
                        start_pos=block_start_pos,
                        end_pos=block_end_pos,
                        start_line=block_start_line,
                        end_line=j - 1,
                        content=self.content[block_start_pos:block_end_pos]
                    )
                    
                    self.blocks.append(block)
                
                i = j
                current_pos = block_end_pos
            else:
                current_pos += len(line)
                i += 1
    
    def _is_indented_line(self, line: str) -> bool:
        """Check if line is indented for code block.
        
        Args:
            line: Line to check
            
        Returns:
            True if line is indented
        """
        if not line.strip():  # Empty line
            return False
        
        return line.startswith('    ') or line.startswith('\t')


# Global detector instance for reuse
_detector = CodeBlockDetector()


def detect_code_blocks(content: str) -> List[CodeBlock]:
    """Detect all code blocks in content.
    
    Args:
        content: Markdown content
        
    Returns:
        List of detected code blocks
    """
    return _detector.detect_code_blocks(content)


def is_position_in_code_block(content: str, pos: int) -> bool:
    """Check if position is in a code block.
    
    Args:
        content: Markdown content
        pos: Character position
        
    Returns:
        True if position is in code block
    """
    blocks = detect_code_blocks(content)
    for block in blocks:
        if block.start_pos <= pos < block.end_pos:
            return True
    return False


def is_range_in_code_block(content: str, start_pos: int, end_pos: int) -> bool:
    """Check if range is entirely in a code block.
    
    Args:
        content: Markdown content
        start_pos: Start position
        end_pos: End position
        
    Returns:
        True if entire range is in code block
    """
    blocks = detect_code_blocks(content)
    for block in blocks:
        if block.start_pos <= start_pos and end_pos <= block.end_pos:
            return True
    return False 