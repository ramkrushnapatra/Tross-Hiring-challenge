class ScraperError(Exception):
  """Raised when scraping fails with a machine-readable error code."""

  def __init__(self, message: str, code: str = "SCRAPER_ERROR"):
    super().__init__(message)
    self.code = code
