"""<internal>"""

'''
zlib License

(C) 2020-2022 DeltaRazero
All rights reserved.
'''

# ***************************************************************************************

class __:
    '<imports>'

    import pathlib as pl
    import typing  as t
    import sys
    import warnings

    from ._textstream_core import (
        ITextstream,
        AbstractTextstream,
    )

# ***************************************************************************************

_SYSTEM_ENCODING = __.sys.stdin.encoding

# ***************************************************************************************

class Textstream_Disk (__.AbstractTextstream, __.ITextstream):
    """Abstract base class of an ITextstream implementation.
    """

  # --- FIELDS --- #

    _encoding : str
    _f_isEof  : bool
    _f : __.t.IO[bytes]

    # NOTE: To clarify, _bufferSize is the the amount of bytes, while _bufferStringSize
    # is be the amount of decoded characters, i.e. character codepoints.
    _buffer : bytes
    _bufferSize : int

    _undecodedBytes : bytes
    _undecodedBytesSize : int

    _bufferStringSplit : int


  # --- CONSTRUCTOR & DESTRUCTOR --- #

    def __init__(self,
                 fp: __.t.Union[str, __.pl.Path],
                 bufferSize: int,
                 encoding: str,
                 convertLineEndings: bool,
    ) -> None:
        """TextPosition object instance initializer.

        Parameters
        ----------
        fp : Union[str, Path]
            String or Path object of a textfile to open.
        bufferSize : int
            Size of the buffer used to split a file into segments. Keep in mind that in
            order to completely capture a token, it must be smaller or equal to the size
            allocated to the buffer by this argument. NOTE: this number will be floored
            to the nearest even number.
        encoding : str
            Encoding of text in the file.
        convertLineEndings : bool
            Convert line-endings from Windows style to UNIX style.
        """
        super().__init__()

        self._encoding   = encoding
        self._convertEOL = convertLineEndings

        # Enforce minimum buffer size
        if (bufferSize<256):
            bufferSize=256
            __.warnings.warn(category=RuntimeWarning, message=
                f"Set the buffer size to {bufferSize} as that is the minimum required size to functionally operate."
            )

        self._bufferSize = bufferSize // 2 * 2 # Ensure even number
        self._buffer = bytes()

        self._undecodedBytes = bytes()
        self._undecodedBytesSize = 0

        self._f_isEof = False
        self._f = open(fp, "rb") # pylint: disable=consider-using-with

        self._Read(self._bufferSize)
        self._RefreshBufferStringMeta()

        return


    def __del__(self):
        self.Close()
        return


  # --- INTERFACE METHODS --- #

    def Close(self) -> None:

        if (self._f.closed):
            return

        self._f.close()
        self._buffer       = bytes()
        self._bufferString = ""

        return


    def Update(self, n: int) -> None:

        # TODO?: Technically an exception should be thrown if a program tries to read a
        # negative amount of data, but it a takes an unnecessary performance hit when
        # using the CPython interpreter, so I'd rather not...
        if (n < 1):
            return

        # Can't be possible to read more than the allocated buffer size
        if (n > self._bufferStringSize):
            raise MemoryError("Requested update size is bigger than the allocated buffer string size!")

        self._UpdatePosition(n)

        if (self._f_isEof):
            if (self._bufferStringPos >= self._bufferStringSize):
                self._isEof = True

        elif (self._bufferStringPos > self._bufferStringSplit):

            # Remainder to fill entire string buffer (in bytes)
            remainder = self._bufferSize - self._BinaryStringLength(self._bufferString)

            # Amount of bytes read by the stream
            bytes_read = self._BinaryStringLength(
                self._bufferString[:self._bufferStringPos]
            )

            self._bufferString =\
                self._bufferString[self._bufferStringPos:]\
                +\
                self._Read(bytes_read + remainder)

            self._RefreshBufferStringMeta()

        return


  # --- PRIVATE METHODS --- #

    # @staticmethod
    def _BinaryStringLength(self, s: str) -> int:
        return len(s.encode(self._encoding))

    # NOTE: In the case that only system decoding is needed (which in most cases is going
    # to be UTF-8), then usage of the static method below is encouraged instead.

    # @staticmethod
    # def _BinaryStringLength(s: str) -> int:
    #    return len(s.encode(_SYSTEM_ENCODING))


    def _RefreshBufferStringMeta(self) -> None:

        self._bufferStringPos   = 0
        self._bufferStringSize  = len(self._bufferString)
        self._bufferStringSplit = self._bufferStringSize // 2

        # NOTE: For debugging purposes
        # print(self._BinaryStringLength(self._bufferString))

        return


    def _Read(self, nBytes: int) -> str:

        nBytes -= self._undecodedBytesSize
        if (nBytes < 0):
            raise RuntimeError("Cannot read negative amount of bytes: buffer size is probably too small.")

        temp = self._f.read(nBytes)

        # If the amount of bytes read is lower than given as input, then EOF is reached
        bytes_read = len(temp)
        if (bytes_read < nBytes):
            self._f_isEof = True
            nBytes = bytes_read

        # If some multi-byte encoded characters had missing bytes, insert the already
        # read bytes at the beginning of the buffer. That way multi-byte encoded
        # characters can be fully decoded.
        if (self._undecodedBytes):
            self._buffer = self._undecodedBytes + temp
        # Else just move the already read bytes to the buffer
        else:
            self._buffer = temp

        # Decode to a string object with given text encoding
        self._bufferString = self._buffer.decode(encoding=self._encoding, errors="ignore")
        if (self._convertEOL):
            self._bufferString = self._bufferString.replace("\r", "")

        # In case multi-byte characters are present, some characters may not have been
        # decoded (at the end). We keep those undecoded bytes and insert them at the
        # beginning of the next buffer when updating.
        n_undecoded_bytes = nBytes - self._BinaryStringLength(self._bufferString) + self._undecodedBytesSize
        # If converting line endings, then \r bytes that are filtered out don't count
        # towards this number
        if (self._convertEOL):
            n_undecoded_bytes -= self._buffer.count(b"\r\n")

        if (n_undecoded_bytes):
            self._undecodedBytes     = self._buffer[-n_undecoded_bytes:]
            self._undecodedBytesSize = n_undecoded_bytes
        else:
            # No need to re-init if already empty
            if (self._undecodedBytes):
                self._undecodedBytes     = bytes()
                self._undecodedBytesSize = 0

        return self._bufferString
