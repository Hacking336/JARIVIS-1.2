from dataclasses import dataclass
from typing import Dict, List, Optional, Set
from enum import Enum
import json


class PermissionLevel(str, Enum):
    DENY = "deny"
    ALLOW = "allow"
    CONFIRM = "confirm"


class ResourceType(str, Enum):
    SYSTEM = "system"
    EMAIL = "email"
    APPLICATION = "application"
    FILE = "file"
    SETTING = "setting"
    REMINDER = "reminder"
    NOTE = "note"


@dataclass
class PermissionRule:
    resource_type: ResourceType
    action: str
    level: PermissionLevel
    conditions: Dict[str, any] = None


@dataclass
class PermissionResult:
    allowed: bool
    level: PermissionLevel
    reason: str
    requires_confirmation: bool = False


class PermissionManager:
    def __init__(self):
        self._rules: List[PermissionRule] = []
        self._approved_apps: Set[str] = set()
        self._approved_directories: Set[str] = set()
        self._blocked_processes: Set[str] = set()
        self._load_default_rules()

    def _load_default_rules(self):
        self._blocked_processes = {
            "system", "registry", "smss", "csrss", "wininit", "winlogon",
            "services", "lsass", "lsm", "svchost", "fontdrvhost", "dwm",
            "taskhost", "explorer", "startmenuexperiencehost",
        }

        self._rules = [
            PermissionRule(ResourceType.SYSTEM, "read_status", PermissionLevel.ALLOW),
            PermissionRule(ResourceType.SYSTEM, "read_processes", PermissionLevel.ALLOW),
            PermissionRule(ResourceType.SYSTEM, "terminate_process", PermissionLevel.CONFIRM,
                         conditions={"blocked_processes": self._blocked_processes}),

            PermissionRule(ResourceType.EMAIL, "read", PermissionLevel.ALLOW),
            PermissionRule(ResourceType.EMAIL, "search", PermissionLevel.ALLOW),
            PermissionRule(ResourceType.EMAIL, "draft", PermissionLevel.ALLOW),
            PermissionRule(ResourceType.EMAIL, "send", PermissionLevel.CONFIRM),

            PermissionRule(ResourceType.APPLICATION, "launch", PermissionLevel.ALLOW,
                         conditions={"approved_only": True, "approved_apps": self._approved_apps}),
            PermissionRule(ResourceType.APPLICATION, "terminate", PermissionLevel.CONFIRM),

            PermissionRule(ResourceType.FILE, "search", PermissionLevel.ALLOW,
                         conditions={"approved_directories": self._approved_directories}),
            PermissionRule(ResourceType.FILE, "read", PermissionLevel.CONFIRM),
            PermissionRule(ResourceType.FILE, "write", PermissionLevel.CONFIRM),
            PermissionRule(ResourceType.FILE, "delete", PermissionLevel.DENY),

            PermissionRule(ResourceType.SETTING, "read", PermissionLevel.ALLOW),
            PermissionRule(ResourceType.SETTING, "write", PermissionLevel.CONFIRM),

            PermissionRule(ResourceType.REMINDER, "create", PermissionLevel.ALLOW),
            PermissionRule(ResourceType.REMINDER, "read", PermissionLevel.ALLOW),
            PermissionRule(ResourceType.REMINDER, "update", PermissionLevel.ALLOW),
            PermissionRule(ResourceType.REMINDER, "delete", PermissionLevel.ALLOW),

            PermissionRule(ResourceType.NOTE, "create", PermissionLevel.ALLOW),
            PermissionRule(ResourceType.NOTE, "read", PermissionLevel.ALLOW),
            PermissionRule(ResourceType.NOTE, "update", PermissionLevel.ALLOW),
            PermissionRule(ResourceType.NOTE, "delete", PermissionLevel.ALLOW),
        ]

    def check_permission(
        self,
        resource_type: ResourceType,
        action: str,
        context: Optional[Dict[str, any]] = None,
    ) -> PermissionResult:
        context = context or {}

        for rule in self._rules:
            if rule.resource_type == resource_type and rule.action == action:
                if rule.level == PermissionLevel.ALLOW:
                    if self._check_conditions(rule.conditions, context):
                        return PermissionResult(
                            allowed=True,
                            level=PermissionLevel.ALLOW,
                            reason="Allowed by policy",
                        )
                    else:
                        return PermissionResult(
                            allowed=False,
                            level=PermissionLevel.DENY,
                            reason="Conditions not met",
                        )

                elif rule.level == PermissionLevel.CONFIRM:
                    if self._check_conditions(rule.conditions, context):
                        return PermissionResult(
                            allowed=True,
                            level=PermissionLevel.CONFIRM,
                            reason="Requires user confirmation",
                            requires_confirmation=True,
                        )
                    else:
                        return PermissionResult(
                            allowed=False,
                            level=PermissionLevel.DENY,
                            reason="Conditions not met",
                        )

                elif rule.level == PermissionLevel.DENY:
                    return PermissionResult(
                        allowed=False,
                        level=PermissionLevel.DENY,
                        reason="Denied by policy",
                    )

        return PermissionResult(
            allowed=False,
            level=PermissionLevel.DENY,
            reason="No matching rule found",
        )

    def _check_conditions(self, conditions: Optional[Dict], context: Dict) -> bool:
        if not conditions:
            return True

        if "approved_only" in conditions and conditions["approved_only"]:
            app = context.get("application", "").lower()
            approved = conditions.get("approved_apps", set())
            if app and app not in approved:
                return False

        if "approved_directories" in conditions:
            path = context.get("path", "")
            approved_dirs = conditions.get("approved_directories", set())
            if path and not any(path.startswith(d) for d in approved_dirs):
                return False

        if "blocked_processes" in conditions:
            process = context.get("process", "").lower()
            blocked = conditions.get("blocked_processes", set())
            if process in blocked:
                return False

        return True

    def add_approved_app(self, app_name: str):
        self._approved_apps.add(app_name.lower())

    def remove_approved_app(self, app_name: str):
        self._approved_apps.discard(app_name.lower())

    def get_approved_apps(self) -> Set[str]:
        return self._approved_apps.copy()

    def add_approved_directory(self, path: str):
        self._approved_directories.add(path)

    def remove_approved_directory(self, path: str):
        self._approved_directories.discard(path)

    def get_approved_directories(self) -> Set[str]:
        return self._approved_directories.copy()

    def add_blocked_process(self, process_name: str):
        self._blocked_processes.add(process_name.lower())

    def get_blocked_processes(self) -> Set[str]:
        return self._blocked_processes.copy()

    def add_custom_rule(self, rule: PermissionRule):
        self._rules.append(rule)

    def remove_rule(self, resource_type: ResourceType, action: str):
        self._rules = [r for r in self._rules if not (r.resource_type == resource_type and r.action == action)]

    def get_rules(self) -> List[PermissionRule]:
        return self._rules.copy()

    def export_policy(self) -> str:
        policy = {
            "approved_apps": list(self._approved_apps),
            "approved_directories": list(self._approved_directories),
            "blocked_processes": list(self._blocked_processes),
            "rules": [
                {
                    "resource_type": r.resource_type.value,
                    "action": r.action,
                    "level": r.level.value,
                    "conditions": {
                        k: list(v) if isinstance(v, set) else v
                        for k, v in (r.conditions or {}).items()
                    },
                }
                for r in self._rules
            ],
        }
        return json.dumps(policy, indent=2)

    def import_policy(self, policy_json: str):
        policy = json.loads(policy_json)
        self._approved_apps = set(policy.get("approved_apps", []))
        self._approved_directories = set(policy.get("approved_directories", []))
        self._blocked_processes = set(policy.get("blocked_processes", []))

        for rule_data in policy.get("rules", []):
            conditions = rule_data.get("conditions")
            if conditions:
                conditions = {
                    k: set(v) if isinstance(v, list) else v
                    for k, v in conditions.items()
                }
            rule = PermissionRule(
                resource_type=ResourceType(rule_data["resource_type"]),
                action=rule_data["action"],
                level=PermissionLevel(rule_data["level"]),
                conditions=conditions,
            )
            self.add_custom_rule(rule)