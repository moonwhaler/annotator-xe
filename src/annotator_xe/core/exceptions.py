"""Custom exception hierarchy for Annotator XE."""


class AnnotatorError(Exception):
    """Base exception for Annotator XE."""
    pass


class AnnotationFormatError(AnnotatorError):
    """Error related to annotation format operations."""
    pass


class InvalidFormatError(AnnotationFormatError):
    """The annotation format is invalid or corrupted."""
    pass


class UnsupportedFormatError(AnnotationFormatError):
    """The annotation format is not supported."""
    pass


class ValidationError(AnnotatorError):
    """Data validation failed."""
    pass


class ProjectError(AnnotatorError):
    """Error related to project operations."""
    pass


class DetectionError(AnnotatorError):
    """Error related to object detection."""
    pass
