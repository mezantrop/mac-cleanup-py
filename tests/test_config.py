"""All tests for mac_clean_up.config"""
from typing import Optional, Callable, IO

import pytest
from _pytest.capture import CaptureFixture
from _pytest.monkeypatch import MonkeyPatch

import tempfile

import toml

from pathlib import Path

from inquirer.errors import EndOfInput  # pyright: ignore [reportMissingTypeStubs, reportUnknownVariableType]
from readchar import key

from mac_cleanup.config import Config, ConfigFile


@pytest.mark.parametrize(
    "enabled",
    [1, 2]
)
def test_config_init_enabled(
        enabled: int
):
    # Set list of dummy modules
    enabled_modules = [f"test{num}" for num in range(enabled)]

    # Create dummy ConfigFile
    test_config = ConfigFile(enabled=enabled_modules, custom_path=None)

    with tempfile.NamedTemporaryFile(mode="w+") as f:
        # Write dummy file
        toml.dump(test_config, f)

        # Flush from buffer
        f.flush()
        # Move pointer to start of file
        f.seek(0)

        # Get tmp file path
        config_path = Path(f.name)
        # Load config from dummy file
        config = Config(config_path_=config_path)

        # Assert that dummy modules loaded
        assert len(config.get_config_data.get("enabled")) == len(enabled_modules)  # noqa


@pytest.mark.parametrize(
    "custom_path",
    [None, "/test"]
)
def test_config_init_custom_path(
        custom_path: Optional[str]
):
    # Create dummy ConfigFile
    test_config = ConfigFile(enabled=["test"], custom_path=custom_path)

    with tempfile.NamedTemporaryFile(mode="w+") as f:
        # Write dummy file
        toml.dump(test_config, f)

        # Flush from buffer
        f.flush()
        # Move pointer to start of file
        f.seek(0)

        # Get tmp file path
        config_path = Path(f.name)
        # Load config from dummy file
        config = Config(config_path_=config_path)

        # Assert that custom path is correct
        assert config.get_custom_path == custom_path  # noqa


@pytest.fixture(
    scope="session"
)
def user_output() -> list[str]:
    """Set dummy user output"""

    return [f"test{num}" for num in range(2)]


@pytest.fixture(
    scope="session"
)
def dummy_module() -> Callable[..., None]:
    """Dummy module for calling modules in __call__"""

    return lambda: None


@pytest.fixture(
    scope="session"
)
def dummy_prompt(
        user_output: list[str]
) -> Callable[..., None]:
    """Dummy prompt for inquirer (args are needed for params being provided to inquirer)"""

    def inner(*args: list[str] | bool) -> None:  # noqa
        raise EndOfInput(user_output)

    return inner


@pytest.fixture(
    scope="session"
)
def dummy_key() -> Callable[..., str]:
    """Dummy key press for inquirer"""

    return lambda: key.ENTER


def config_call_final_checks(
        config: Config,
        configuration_prompted: bool,
        file_context: IO[str],
        capsys: CaptureFixture[str],
        monkeypatch: MonkeyPatch,
        user_output: list[str],
        dummy_module: Callable[..., None],
        dummy_prompt: Callable[..., None],
        dummy_key: Callable[..., str]
):
    # Simulate dummy modules are legit
    for out in user_output:
        monkeypatch.setitem(config.get_modules, out, dummy_module)  # noqa

    # Simulate user input to enable a module
    monkeypatch.setattr("inquirer.render.console._checkbox.Checkbox.process_input", dummy_prompt)
    monkeypatch.setattr("readchar.readkey", dummy_key)

    # Check error being raised on configuration prompt
    if configuration_prompted:
        with pytest.raises(SystemExit):
            config(configuration_prompted=configuration_prompted)

        # Get stdout
        captured_stdout = capsys.readouterr().out
    else:
        config(configuration_prompted=configuration_prompted)

        # Get stdout
        captured_stdout = capsys.readouterr().out

        # Check message on empty config
        assert "Modules not configured" in captured_stdout

    # Flush from buffer (new config)
    file_context.flush()
    # Move pointer to start of file
    file_context.seek(0)

    # Check legend being printed to user
    assert "Enable" in captured_stdout
    assert "Confirm" in captured_stdout
    assert "Controls" in captured_stdout

    # Check modules list being printed to user
    assert "Active modules" in captured_stdout

    # Check that the config file was written correctly
    config_data = ConfigFile(**toml.load(file_context))

    # Check new config is correct
    assert (
            config.get_config_data.get("enabled")  # noqa
            == config_data.get("enabled")
            == user_output
    )


def test_config_call_configuration_prompted(
        user_output: list[str],
        dummy_module: Callable[..., None],
        dummy_prompt: Callable[..., None],
        dummy_key: Callable[..., str],
        capsys: CaptureFixture[str],
        monkeypatch: MonkeyPatch
):
    # Create dummy ConfigFile
    test_config = ConfigFile(enabled=["test"], custom_path=None)

    with tempfile.NamedTemporaryFile(mode="w+") as f:
        # Write dummy config to tmp file
        toml.dump(test_config, f)

        # Flush from buffer
        f.flush()
        # Move pointer to start of file
        f.seek(0)

        # Get tmp file path
        config_path = Path(f.name)
        # Load config with tmp path
        config = Config(config_path_=config_path)

        # Check default state
        assert (
                config.get_config_data.get("enabled")  # noqa
                == ConfigFile(**toml.load(f)).get("enabled")
                == ["test"]
        )

        # Launch final check
        config_call_final_checks(
            config=config,
            configuration_prompted=True,
            file_context=f,
            capsys=capsys,
            monkeypatch=monkeypatch,
            user_output=user_output,
            dummy_module=dummy_module,
            dummy_prompt=dummy_prompt,
            dummy_key=dummy_key
        )


def test_config_call_with_no_config(
        user_output: list[str],
        dummy_module: Callable[..., None],
        dummy_prompt: Callable[..., None],
        dummy_key: Callable[..., str],
        capsys: CaptureFixture[str],
        monkeypatch: MonkeyPatch
):
    # Create empty config
    test_config: dict[str, list[str] | Optional[str]] = dict()

    with tempfile.NamedTemporaryFile(mode="w+") as f:
        # Write dummy config to tmp file
        toml.dump(test_config, f)

        # Flush from buffer
        f.flush()
        # Move pointer to start of file
        f.seek(0)

        # Get tmp file path
        config_path = Path(f.name)
        # Load config with tmp path
        config = Config(config_path_=config_path)

        # Check default state
        assert (
                config.get_config_data.get("enabled")  # noqa
                is ConfigFile(**toml.load(f)).get("enabled")
                is None
        )

        # Launch final check
        config_call_final_checks(
            config=config,
            configuration_prompted=False,
            file_context=f,
            capsys=capsys,
            monkeypatch=monkeypatch,
            user_output=user_output,
            dummy_module=dummy_module,
            dummy_prompt=dummy_prompt,
            dummy_key=dummy_key
        )


@pytest.mark.parametrize(
    "custom_path",
    ["~/Documents/my-custom-modules", None]
)
def test_configure_custom_path(
        custom_path: Optional[str],
        monkeypatch: MonkeyPatch
):
    # Set default custom modules path
    default_path = "~/Documents/mac-cleanup/"

    # Dummy user input
    dummy_input: Callable[..., str] = lambda: custom_path if custom_path else ""

    with tempfile.NamedTemporaryFile(mode="w+") as f:
        # Get tmp file path
        config_path = Path(f.name)
        # Load config from dummy file
        config = Config(config_path)

        # Simulate user input with custom path
        monkeypatch.setattr("builtins.input", dummy_input)

        # Call for custom path configuration
        config.set_custom_path()

        # Flush from buffer
        f.flush()
        # Move pointer to start of file
        f.seek(0)

        if not custom_path:
            custom_path = default_path

        custom_path = Path(custom_path).expanduser().as_posix()

        # Check that the custom path was written to the config file
        config_data = ConfigFile(**toml.load(f))

        assert config_data.get("custom_path") == custom_path


def test_config_init_no_file():
    pass


def test_config_call_with_custom_modules():
    pass


def test_config_empty_modules():
    pass
