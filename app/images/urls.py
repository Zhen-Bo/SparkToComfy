def image_urls(prompt_id: str, refs: list[dict]) -> list[str]:
    return [f"/v1/images/{prompt_id}?index={i}" for i in range(len(refs))]
