"""
Simple pipelines
````````````````

Simple pipelines
""" 
import csv
from pomp.core.base import BasePipeline
from pomp.core.utils import isstring


class CsvPipeline(BasePipeline):
    """Save items to CSV format

    Params `*args` and `**kwargs` passed to ``csv.writer`` constuctor.

    :param output_file: filename of file like object. If `output_file` is file
                        like object then after pipe stoped file will be
                        not closed
    """

    def __init__(self, output_file, *args, **kwargs):
        self.output_file = output_file
        self._csv_args = args
        self._csv_kwargs = kwargs

        # no close file if it not opened by this instance
        self._need_close = False


    def start(self):
        if isstring(self.output_file):
            self.csvfile = open(self.output_file, 'a', newline='')
            self._need_close = True
        else:
            self.csvfile = self.output_file

        self.writer = csv.writer(
            self.csvfile, *self._csv_args, **self._csv_kwargs
        )

    def process(self, item):
        self.writer.writerow(list(item.values()))
        return item

    def stop(self):
        if self._need_close:
            self.csvfile.close()