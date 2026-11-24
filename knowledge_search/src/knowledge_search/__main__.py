from sdlc_service import serve

from knowledge_search import DEFAULT_PORT, SERVICE, create_service


def main() -> None:
    serve(create_service(), SERVICE, DEFAULT_PORT)


if __name__ == "__main__":
    main()
