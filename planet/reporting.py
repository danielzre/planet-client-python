# Copyright 2020 Planet Labs, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.
"""Functionality for reporting progress."""
from tqdm.asyncio import tqdm


class ProgressBar():
    def __init__(self):
        self.bar = None

    def __str__(self):
        return str(self.bar)

    def __enter__(self):
        self.open_bar()
        return self

    def __exit__(self, *args):
        self.bar.close()

    def open_bar(self):
        """Initialize and start the progress bar."""
        return NotImplementedError


class StateBar(ProgressBar):
    """Bar reporter of order state.

    Example:
        ```python
        from planet import reporting

        with reporting.StateBar(state='creating') as bar:
            bar.update(state='created', order_id='oid')
            ...
        ```
    """
    def __init__(
        self,
        order_id: str = None,
        state: str = None
    ):
        """Initialize the object.

        Parameters:
            filename: Name of file to display.
            size: File size in bytes.
            unit: Value to scale number of report iterations.
                (e.g. 1024*1024 scales to reporting in Megabytes.)
        """

        self.state = state or ''
        self.order_id = order_id or ''
        super().__init__()

    def open_bar(self):
        """Initialize and start the progress bar."""
        self.bar = tqdm(
            bar_format="{elapsed} - {desc} - {postfix[0]}: {postfix[1]}",
            desc=self.desc, postfix=["state", self.state])

    @property
    def desc(self):
        return f'order {self.order_id}'

    def update(self, state=None, order_id=None, logger=None):
        if state:
            self.state = state
            self.bar.postfix[1] = self.state

        if order_id:
            self.order_id = order_id
            self.bar.set_description_str(self.desc, refresh=False)

        self.bar.refresh()

        if logger:
            logger(str(self.bar))


class FileDownloadBar(ProgressBar):
    """Bar reporter of file download progress.

    Example:
        ```python
        from planet import reporting

        with reporting.FileDownloadBar('img.tif', 100000) as bar:
            bar.update(1000)
            ...
        ```
    """

    def __init__(
        self,
        filename: str,
        size: int,
        unit: int = None
    ):
        """Initialize the object.

        Parameters:
            filename: Name of file to display.
            size: File size in bytes.
            unit: Value to scale number of report iterations.
                (e.g. 1024*1024 scales to reporting in Megabytes.)
        """
        self.filename = filename
        self.size = size
        self.unit = unit or 1024*1024
        super().__init__()

    def open_bar(self):
        """Initialize and start the progress bar."""
        self.bar = tqdm(
            total=self.size,
            unit_scale=True,
            unit_divisor=self.unit,
            unit='B',
            desc=self.filename)

    def update(self, downloaded_amt, logger=None):
        self.bar.update(downloaded_amt)

        if logger:
            logger(str(self.bar))


class OrderDownloadBar(ProgressBar):
    def __init__(
        self,
        order_id: str = None,
        num_files: int = None
    ):
        self.order_id = order_id or ''
        self.num_files = num_files or 0
        super().__init__()

        self.file_bars = []

    def open_bar(self):
        """Initialize and start the progress bar."""
        self.bar = tqdm(
            range(self.num_files),
            desc=self.order_id)

    @property
    def desc(self):
        return f'order {self.order_id}'

    def update(
        self,
        order_id: str = None,
        num_files: int = None,
        add_file: bool = False,
        logger=None
    ):
        if order_id:
            self.order_id = order_id
            self.bar.set_description_str(self.desc, refresh=False)

        if num_files:
            self.bar.total = num_files

        self.bar.refresh()

        if logger:
            logger(str(self.bar))

    #     if add_file:
    #         self.file_bars.append(
    #         return self.create_file_reporter
    #
    # from contextlib import contextmanager
    # @contextmanager
    # def create_file_reporter(self, filename, size, unit=None):
    #     new_bar = FileDownloadBar(filename, size, unit)
    #     new_bar.open()
    #
    #     with FileDownloadBar(filename, size, unit) as bar:
    #         yield bar.update
