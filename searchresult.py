class SearchResult():
    """
    Represents result of searching the memberlist for some members.
    """
    def __init__(self):
        # results from current members sheet
        self.current_results = list()
        # results from old members sheet
        self.old_results = list()
        # results from banned sheet
        self.banned_results = list()
    def __add__(self, other):
        if not isinstance(other, SearchResult):
            raise TypeError
        result = SearchResult()
        # combine without duplicates (checks entry ids)
        for m in self.current_results + other.current_results:
            if m not in result.current_results:
                result.current_results.append(m)
        for m in self.old_results + other.old_results:
            if m not in result.old_results:
                result.old_results.append(m)
        for m in self.banned_results + other.banned_results:
            if m not in result.banned_results:
                result.banned_results.append(m)
        return result
    def combined_list(self):
        """
        Returns a list of combined search results ordered as current > retired > kicked members
        """
        return self.current_results + self.old_results + self.banned_results
    def has_exact(self):
        for memb in self.combined_list():
            if (memb.result_type == "exact"):
                return True
        return False
    def has_old_name(self):
        for memb in self.combined_list():
            if (memb.result_type == "old name"):
                return True
        return False
    def has_result(self):
        if (len(self.combined_list()) > 0):
            return True
        return False
    def has_ban(self):
        if (len(self.banned_results) > 0):
            return True
        return False
    def get_exact(self):
        """
        Returns the first exact match from the search. Ordered as current > retired > kicked members
        """
        for x in self.combined_list():
            if (x.result_type == "exact"):
                return x
        return None