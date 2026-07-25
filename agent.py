def understand_user_request(user_prompt):
    """
    This function takes the user's animation request
    and decides what kind of animation they want.
    """

    prompt = user_prompt.lower()

    if "circle" in prompt and "square" in prompt:
        return "circle_to_square"

    elif "text" in prompt or "write" in prompt:
        return "text_animation"

    elif "equation" in prompt or "math" in prompt:
        return "math_animation"

    else:
        return "unknown"