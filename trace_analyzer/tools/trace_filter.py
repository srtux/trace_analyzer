from typing import List, Optional, Union

class TraceQueryBuilder:
    """
    Builder for Google Cloud Trace filter strings.
    
    See: https://docs.cloud.google.com/trace/docs/trace-filters
    """
    
    def __init__(self):
        self._terms: List[str] = []

    def _add_term(self, term: str, root_only: bool = False):
        if root_only:
            self._terms.append(f"^{term}")
        else:
            self._terms.append(term)

    def span_name(self, name: str, match_exact: bool = False, root_only: bool = False) -> 'TraceQueryBuilder':
        """
        Filter by span name.
        
        Args:
            name: The span name to filter for.
            match_exact: If True, uses `+span:name` (or `+root:name` if root_only).
            root_only: If True, restricts to root span (uses `root:` or `^span:` syntax).
        """
        # "root:[NAME]" is strictly for root span name.
        # "span:[NAME]" is for any span.
        # "^span:[NAME]" is equivalent to "root:[NAME]".
        
        # Let's use the canonical forms if possible.
        prefix = "+" if match_exact else ""
        
        if root_only:
            term = f"root:{name}"
        else:
            term = f"span:{name}"
            
        self._terms.append(f"{prefix}{term}")
        return self

    def latency(self, min_latency_ms: Optional[int] = None, max_latency_ms: Optional[int] = None) -> 'TraceQueryBuilder':
        """
        Filter by latency.
        
        Args:
            min_latency_ms: Minimum latency in milliseconds (>=).
            max_latency_ms: Maximum latency in milliseconds (<=). (Not directly supported by standard syntax?)           
        """
        if min_latency_ms is not None:
             self._terms.append(f"latency:{min_latency_ms}ms")
        
        if max_latency_ms is not None:
            pass
            
        return self

    def attribute(self, key: str, value: str, match_exact: bool = False, root_only: bool = False) -> 'TraceQueryBuilder':
        """
        Filter by attribute (label) key/value.
        
        Args:
            key: Attribute key (e.g. '/http/status_code').
            value: Attribute value.
            match_exact: If True, requires exact match for value (and key).
            root_only: If True, restricts to root span.
        """
        # syntax: key:value
        # exact: +key:value
        # root: ^key:value
        
        term = f"{key}:{value}"
        
        prefix = ""
        if match_exact:
            prefix += "+"
        if root_only:
            # ^ must come before the term but after +?
            # Docs: "+^" is converted to "^+".
            # Docs: "^label:[LABEL_KEY]"
            # Docs: "+^url:[VALUE]"
            prefix += "^"
            
        self._terms.append(f"{prefix}{term}")
        return self

    def service_name(self, name: str, match_exact: bool = False) -> 'TraceQueryBuilder':
        """Helper for service name (usual label 'g.co/gae/app/module' or similar in AppEngine, but OpenTelemetry 'service.name' might map to a custom label)."""
        # Using generic attribute for flexibility.
        # In Google Cloud Trace, service name is often tied to the resource or a specific label.
        # Often `g.co/gae/app/module` or `g.co/run/service`.
        # But if using OpenTelemetry, it might be `service.name` as a label?
        # Trace API v2 treats some things as resources.
        # Simple label approach:
        return self.attribute("service.name", name, match_exact=match_exact)

    def status(self, code: int, root_only: bool = False) -> 'TraceQueryBuilder':
        """Filter by HTTP status code."""
        # /http/status_code
        return self.attribute("/http/status_code", str(code), root_only=root_only)
    
    def method(self, method: str, root_only: bool = False) -> 'TraceQueryBuilder':
         """Filter by HTTP method."""
         # /http/method
         # Shortcut exists: method:GET
         term = f"method:{method}"
         if root_only:
             term = f"^{term}"
         self._terms.append(term)
         return self

    def url(self, url: str, root_only: bool = False) -> 'TraceQueryBuilder':
        """Filter by URL."""
        # /http/url
        # Shortcut: url:VALUE
        term = f"url:{url}"
        if root_only:
            term = f"^{term}"
        self._terms.append(term)
        return self

    def build(self) -> str:
        """Returns the constructed filter string."""
        return " ".join(self._terms)

    def clear(self):
        self._terms = []
