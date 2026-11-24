from sdlc_service import serve

from knowledge_search import DEFAULT_PORT, SERVICE, create_app


def main() -> None:
    serve(create_app(), SERVICE, DEFAULT_PORT)


if __name__ == "__main__":
    main()
