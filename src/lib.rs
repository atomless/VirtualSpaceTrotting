use spin_sdk::http::{Request, Response};
use spin_sdk::http_component;

pub fn health_response() -> &'static str {
    "VirtualSpaceTrotting OK\n"
}

#[http_component]
fn handle(_req: Request) -> Response {
    Response::builder()
        .status(200)
        .header("content-type", "text/plain; charset=utf-8")
        .body(health_response())
        .build()
}

#[cfg(test)]
mod tests {
    use super::health_response;

    #[test]
    fn health_response_identifies_runtime() {
        assert_eq!(health_response(), "VirtualSpaceTrotting OK\n");
    }
}
