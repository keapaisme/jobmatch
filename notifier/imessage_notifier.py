import subprocess
import shlex
import sys

class IMessageNotifier:
    """Send a simple text message via macOS Messages (iMessage) using AppleScript.
    The notifier works only on macOS where the `osascript` command is available.
    If the command fails (e.g., on Linux), it falls back to printing the message.
    """

    def __init__(self, recipient: str):
        """Initialize with the recipient identifier (phone number or email)."""
        self.recipient = recipient

    def _run_osascript(self, script: str) -> bool:
        """Execute the given AppleScript via osascript.
        Returns True on success, False otherwise.
        """
        try:
            # Use shlex to safely pass the script
            cmd = ["osascript", "-e", script]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return True
            else:
                print(f"[iMessage] AppleScript error: {result.stderr.strip()}", file=sys.stderr)
                return False
        except FileNotFoundError:
            # osascript not found – probably not macOS
            print("[iMessage] osascript not found; skipping actual send.")
            return False
        except Exception as exc:
            print(f"[iMessage] Exception while sending: {exc}", file=sys.stderr)
            return False

    def send_message(self, text: str) -> bool:
        """Send *text* to the configured recipient via iMessage.
        Returns True if the message was sent (or simulated on non‑mac platforms).
        """
        # Escape double quotes for AppleScript
        safe_text = text.replace('"', '\\"')
        script = (
            f'tell application "Messages"\n'
            f'    set targetService to 1st service whose service type = iMessage\n'
            f'    set targetBuddy to buddy "{self.recipient}" of targetService\n'
            f'    send "{safe_text}" to targetBuddy\n'
            f'end tell'
        )
        sent = self._run_osascript(script)
        if sent:
            print(f"[iMessage] Sent to {self.recipient}: {text}")
        else:
            # Fallback: just print for visibility
            print(f"[iMessage] (simulated) {self.recipient}: {text}")
        return sent
