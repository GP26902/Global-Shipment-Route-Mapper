"""In-memory stand-in for a gspread worksheet (the parts SheetStore uses)."""
import re


class FakeWorksheet:
    def __init__(self, fail: bool = False):
        self.rows = []            # list of lists of cell values
        self.fail = fail
        self.append_calls = 0
        self.last_append_option = None

    def _check(self):
        if self.fail:
            raise RuntimeError("simulated network failure")

    def row_values(self, n):
        self._check()
        return list(self.rows[n - 1]) if len(self.rows) >= n else []

    def get_all_values(self):
        self._check()
        return [list(r) for r in self.rows]

    def col_values(self, n):
        self._check()
        return [r[n - 1] if len(r) >= n else "" for r in self.rows]

    def append_rows(self, values, value_input_option="RAW", **_):
        self._check()
        self.append_calls += 1
        self.last_append_option = value_input_option
        self.rows.extend([list(v) for v in values])

    def batch_update(self, data, value_input_option=None, **_):
        self._check()
        for item in data:
            m = re.fullmatch(r"([A-Z]+)(\d+)(?::([A-Z]+)(\d+))?", item["range"])
            col = self._col_index(m.group(1))
            row = int(m.group(2))
            vals = item["values"]
            while len(self.rows) < row:
                self.rows.append([])
            for j, v in enumerate(vals[0]):
                r = self.rows[row - 1]
                while len(r) <= col + j:
                    r.append("")
                r[col + j] = v

    @staticmethod
    def _col_index(letters):
        n = 0
        for ch in letters:
            n = n * 26 + ord(ch) - 64
        return n - 1
