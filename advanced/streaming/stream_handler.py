# stream_handler.py — Streaming response processor
class StreamHandler:
    """
    Wraps a backend's stream() generator.
    Calls on_token(token) for each token and on_complete(full_text) at the end.
    """

    def __init__(self, on_token=None, on_complete=None):
        self.on_token = on_token or (lambda t: None)
        self.on_complete = on_complete or (lambda t: None)

    def process(self, stream) -> str:
        """
        Consume a stream generator, fire callbacks, and return full text.

        Args:
            stream: generator yielding str tokens (from backend.stream())

        Returns:
            Complete assembled response string.
        """
        buffer = []
        for token in stream:
            buffer.append(token)
            self.on_token(token)
        full_text = "".join(buffer)
        self.on_complete(full_text)
        return full_text
    