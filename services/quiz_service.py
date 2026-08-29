from utils.engine.free_quiz_pipeline import generate_free_quiz


def create_quiz(
    youtube_url: str,
    use_cache: bool = True,
):
    return generate_free_quiz(
        youtube_url,
        use_cache=use_cache,
    )