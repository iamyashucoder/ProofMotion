from proofmotion.rendering.router import choose_renderer


def test_rosette_uses_the_authored_manimgl_template() -> None:
    choice = choose_renderer("Animate this sinusoidal polar rosette like a spirograph.")

    assert choice.backend == "manimgl"
    assert choice.template == "advanced_polar_rosette.py"


def test_gpu_heavy_generated_request_uses_community_opengl() -> None:
    choice = choose_renderer("Show a 3D vector field with a camera orbit.")

    assert choice.backend == "community-opengl"
    assert choice.template is None


def test_thomas_attractor_uses_the_open_gl_template() -> None:
    choice = choose_renderer("Create a Thomas attractor.")

    assert choice.backend == "community-opengl"
    assert choice.template == "thomas_attractor.py"


def test_rolling_sphere_on_an_incline_uses_the_sparse_physics_template() -> None:
    choice = choose_renderer("A solid sphere rolls without slipping down an inclined plane with two forces.")

    assert choice.backend == "community"
    assert choice.template == "rolling_sphere_incline.py"


def test_nonmatching_manimgl_request_falls_back_to_compatible_opengl() -> None:
    choice = choose_renderer("Explain the chain rule.", requested="manimgl")

    assert choice.backend == "community-opengl"
    assert "no compatible" in choice.reason


def test_standard_request_uses_the_community_renderer() -> None:
    assert choose_renderer("Explain a derivative visually.").backend == "community"
