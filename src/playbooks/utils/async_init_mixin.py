class AsyncInitMixin:
    _ALLOW_INIT = False

    def __init__(self, *args, **kwargs):
        if not self.__class__._ALLOW_INIT:
            raise RuntimeError(
                f"{self.__class__.__name__} cannot be instantiated directly. "
                f"Use 'await {self.__class__.__name__}.create()' instead."
            )
        super().__init__(*args, **kwargs)

    @classmethod
    async def create(cls, *args, **kwargs):
        cls._ALLOW_INIT = True
        try:
            instance = cls(*args, **kwargs)
        finally:
            cls._ALLOW_INIT = False
        await instance._async_init()
        return instance

    async def _async_init(self):
        """Override this method in subclasses for async initialization"""
        pass
