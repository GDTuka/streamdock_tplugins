import importlib
import inspect
import os
import sys
import traceback
from typing import Dict, Optional, Type

from .action import Action
from .logger import Logger


class ActionFactory:
    """Registry of Action subclasses, keyed by lowercase module name.

    The StreamDock action UUID's last segment must match the module name
    (e.g. UUID `com.vscode.cmd.run` → module `src/actions/run.py`).
    """

    _action_types: Dict[str, Type[Action]] = {}

    @classmethod
    def register_action(cls, action_type: str, action_class: Type[Action]):
        cls._action_types[action_type] = action_class

    @classmethod
    def create_action(cls, action: str, context: str, settings: dict, plugin) -> Optional[Action]:
        try:
            action_name = action.split('.')[-1]
            action_class = cls._action_types.get(action_name)
            if action_class is None:
                Logger.error(f"Action type not found: {action_name}")
                return None
            instance = action_class(action, context, settings, plugin)
            if not isinstance(instance, Action):
                Logger.error(f"Created instance is not an Action subclass: {action_name}")
                return None
            return instance
        except Exception as exc:
            Logger.error(f"Error creating action {action}: {exc}")
            Logger.error(traceback.format_exc())
            return None

    @classmethod
    def scan_and_register_actions(cls):
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS  # type: ignore[attr-defined]
            actions_dir = os.path.join(base_path, 'src', 'actions')
        else:
            actions_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 'actions'
            )
        if not os.path.exists(actions_dir):
            Logger.error(f"Actions directory not found: {actions_dir}")
            return

        src_dir = os.path.dirname(actions_dir)
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)

        for file_name in os.listdir(actions_dir):
            if not file_name.endswith('.py') or file_name.startswith('__'):
                continue
            module_name = file_name[:-3]
            try:
                module = importlib.import_module(f'actions.{module_name}')
                Logger.info(f"Loading action module: {module_name}")
                for _name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and issubclass(obj, Action) and obj is not Action:
                        action_type = module_name.lower()
                        cls.register_action(action_type, obj)
                        Logger.info(f"Registered action: {action_type} -> {obj.__name__}")
            except Exception as exc:
                Logger.error(f"Error loading action module {module_name}: {exc}")
                Logger.error(traceback.format_exc())


ActionFactory.scan_and_register_actions()
