import io
import socket
import typing

from headers import Headers

# https://stackoverflow.com/questions/12637768/python-3-send-method-of-generators
def iter_lines(sock: socket.socket, bufsize: int = 16_384) -> typing.Generator[str, None, str]:
    """Given a socket, read all the individual CRLF-separated lines
    and yield each one until an empty one is found.  Returns the
    remainder after the empty line.
    """
    buff = ""
    while True:
        data = sock.recv(bufsize).decode('utf-8')
        print("****", data, "******")
        if not data:
            return ""

        buff += data
        while True:
            try:
                i = buff.index("\r\n")
                line, buff = buff[:i], buff[i + 2:]
                if not line:
                    return buff

                yield line
            except IndexError:
                break


class BodyReader(io.IOBase):
    def __init__(self, sock: socket.socket, *, buff: str = "", bufsize: int = 16_384) -> None:
        self._sock = sock
        self._buff = buff
        self._bufsize = bufsize

    def readable(self) -> bool:
        return True

    def read(self, n: int) -> str:
        """Read up to n number of strs from the request body.
        """
        while len(self._buff) < n:
            data = self._sock.recv(self._bufsize).decode('utf-8')
            if not data:
                break

            self._buff += data

        res, self._buff = self._buff[:n], self._buff[n:]
        return res


class Request(typing.NamedTuple):
    method: str
    path: str
    headers: typing.Mapping[str, str]
    body: BodyReader

    @classmethod
    def from_socket(cls, sock: socket.socket) -> "Request":
        """Read and parse the request from a socket object.

        Raises:
          ValueError: When the request cannot be parsed.
        """
        lines = iter_lines(sock)

        try:
            request_line = next(lines)
        except StopIteration:
            raise ValueError("Request line missing")

        try:
            method, path, _ = request_line.split(" ")
        except ValueError:
            # https://stackoverflow.com/questions/44800801/in-python-format-f-string-strings-what-does-r-mean
            # https://stackoverflow.com/questions/1436703/what-is-the-difference-between-str-and-repr
            raise ValueError(f"Malformed request line {request_line!r}.")

        headers = Headers()
        buff = ""
        while True:
            try:
                line = next(lines)
            except StopIteration as e:
                buff = e.value
                break

            try:
                name, _, value = line.partition(":")
                headers.add(name, value.lstrip())
            except ValueError:
                raise ValueError(f"Malformed header line {line!r}")

        body = BodyReader(sock, buff=buff)
        return cls(method=method.upper(), path=path, headers=headers, body=body)
