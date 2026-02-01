from bazis.core.routing import BazisRouter


router = BazisRouter(prefix="/api/v1")

router.register("demo.router")
router.register("bazis.contrib.async_background.router")
