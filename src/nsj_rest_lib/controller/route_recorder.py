class RouteRecord:
    route_path: str = None
    http_method: str = None
    description: str = None
    route_obj: type = None


class RouteRecorder:
    routes = []
    list_routes = []

    @staticmethod
    def record_route(
        route_path: str,
        http_method: str,
        description: str,
        route_obj: type,
    ):
        route_record = RouteRecord()
        route_record.route_path = route_path
        route_record.http_method = http_method
        route_record.description = description
        route_record.route_obj = route_obj

        RouteRecorder.routes.append(route_record)

        if route_obj.__class__.__name__ == "ListRoute":
            RouteRecorder.list_routes.append(route_record)
