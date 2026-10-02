"""Convert Kubernetes client objects into API JSON dictionaries.

The collector and the demo fixtures both use this camelCase shape.
"""


def to_plain(obj):
    if obj is None or isinstance(obj, dict):
        return obj
    if hasattr(obj, "attribute_map"):
        from kubernetes.client import ApiClient

        return ApiClient().sanitize_for_serialization(obj)
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    raise TypeError(f"Cannot serialize {type(obj).__name__} into a snapshot")
