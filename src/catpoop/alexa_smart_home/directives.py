"""Answer the Smart Home directives Alexa sends: Discovery, AcceptGrant and ReportState."""

import logging
import uuid
from typing import Any, Protocol

from catpoop.alexa_smart_home.sensors import Sensor
from catpoop.clock import Clock

log = logging.getLogger(__name__)


class Grant(Protocol):
    """Trades the linking code for tokens (`Grants`)."""

    def accept(self, code: str) -> None:
        """Save tokens for `code`, or raise."""
        ...


class SmartHome:
    """The Smart Home skill's answers for our virtual sensors."""

    def __init__(self, sensors: list[Sensor], grant: Grant, clock: Clock) -> None:
        """Show `sensors` to Alexa; `grant` handles linking."""
        self._sensors = {s.endpoint_id: s for s in sensors}
        self._grant = grant
        self._clock = clock

    def answer(self, request: dict[str, Any]) -> dict[str, Any]:
        """The response to one directive."""
        directive = request["directive"]
        header = directive["header"]
        name = f"{header['namespace']}.{header['name']}"
        if name == "Alexa.Discovery.Discover":
            endpoints = [_endpoint(s) for s in self._sensors.values()]
            return _event("Alexa.Discovery", "Discover.Response", {"endpoints": endpoints})
        if name == "Alexa.Authorization.AcceptGrant":
            try:
                self._grant.accept(directive["payload"]["grant"]["code"])
            except Exception as error:
                log.warning("Alexa linking failed: %s", error)
                return _error("Alexa.Authorization", "ACCEPT_GRANT_FAILED", str(error))
            return _event("Alexa.Authorization", "AcceptGrant.Response", {})
        endpoint_id = directive.get("endpoint", {}).get("endpointId")
        if name == "Alexa.ReportState" and endpoint_id in self._sensors:
            return self._state(header, endpoint_id)
        return _error("Alexa", "INVALID_DIRECTIVE", f"not supported: {name}")

    def _state(self, header: dict[str, Any], endpoint_id: str) -> dict[str, Any]:
        response = _event("Alexa", "StateReport", {})
        response["event"]["header"]["correlationToken"] = header.get("correlationToken")
        response["event"]["endpoint"] = {"endpointId": endpoint_id}
        response["context"] = {"properties": not_detected(self._clock)}
        return response


def not_detected(clock: Clock) -> list[dict[str, Any]]:
    """The resting state of a sensor: no motion, connected."""
    now = clock.now().strftime("%Y-%m-%dT%H:%M:%S.00Z")
    return [
        _property("Alexa.MotionSensor", "detectionState", "NOT_DETECTED", now),
        _property("Alexa.EndpointHealth", "connectivity", {"value": "OK"}, now),
    ]


def _property(namespace: str, name: str, value: Any, when: str) -> dict[str, Any]:
    return {
        "namespace": namespace,
        "name": name,
        "value": value,
        "timeOfSample": when,
        "uncertaintyInMilliseconds": 0,
    }


def _endpoint(sensor: Sensor) -> dict[str, Any]:
    def interface(name: str, prop: str, reported: bool) -> dict[str, Any]:
        supported = {"supported": [{"name": prop}], "retrievable": True}
        return {
            "type": "AlexaInterface",
            "interface": name,
            "version": "3",
            "properties": {**supported, "proactivelyReported": reported},
        }

    return {
        "endpointId": sensor.endpoint_id,
        "manufacturerName": "catpoop",
        "friendlyName": sensor.name,
        "description": f"Turns on when the {sensor.kind} message is said",
        "displayCategories": ["MOTION_SENSOR"],
        "capabilities": [
            interface("Alexa.MotionSensor", "detectionState", True),
            interface("Alexa.EndpointHealth", "connectivity", False),
            {"type": "AlexaInterface", "interface": "Alexa", "version": "3"},
        ],
    }


def _event(namespace: str, name: str, payload: dict[str, Any]) -> dict[str, Any]:
    header = {
        "namespace": namespace,
        "name": name,
        "payloadVersion": "3",
        "messageId": str(uuid.uuid4()),
    }
    return {"event": {"header": header, "payload": payload}}


def _error(namespace: str, kind: str, message: str) -> dict[str, Any]:
    return _event(namespace, "ErrorResponse", {"type": kind, "message": message})
