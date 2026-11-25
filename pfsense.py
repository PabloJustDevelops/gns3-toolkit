#!/usr/bin/env python3
"""Integración nativa con pfSense 2.7 mediante SSH y ``/conf/config.xml``.

El núcleo no necesita dependencias externas. Las credenciales se inyectan en el
proceso ``sshpass`` sin pasar por un shell local y se redactan de todos los
resultados visibles.
"""
from __future__ import annotations

import base64
import ipaddress
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Callable


class PfSenseError(RuntimeError):
    """Error de configuración o de entorno que impide continuar."""


def _element_to_value(element: ET.Element) -> Any:
    """Convierte XML a diccionarios sin descartar atributos ni etiquetas repetidas."""
    children = list(element)
    attributes = dict(element.attrib)
    if not children and not attributes:
        return element.text or ""

    value: dict[str, Any] = {}
    if attributes:
        value["@attributes"] = attributes
    if element.text and element.text.strip():
        value["#text"] = element.text.strip()
    for child in children:
        tag = child.tag
        converted = _element_to_value(child)
        if tag not in value:
            value[tag] = converted
        elif isinstance(value[tag], list):
            value[tag].append(converted)
        else:
            value[tag] = [value[tag], converted]
    return value


def parse_config(xml: str) -> dict:
    """Parsea un ``config.xml`` de pfSense conservando las secciones desconocidas."""
    try:
        root = ET.fromstring(xml)
    except (ET.ParseError, TypeError) as exc:
        raise PfSenseError(f"config.xml no es XML válido: {exc}") from exc
    if root.tag != "pfsense":
        raise PfSenseError(f"config.xml debe tener raíz <pfsense>, no <{root.tag}>")
    value = _element_to_value(root)
    return value if isinstance(value, dict) else {}


def _fill_element(element: ET.Element, value: Any) -> None:
    if isinstance(value, dict):
        attributes = value.get("@attributes", {})
        if isinstance(attributes, dict):
            element.attrib.update({str(key): str(item) for key, item in attributes.items()})
        if "#text" in value:
            element.text = "" if value["#text"] is None else str(value["#text"])
        for key, item in value.items():
            if key in ("@attributes", "#text"):
                continue
            _add_value(element, str(key), item)
    elif value is not None:
        element.text = str(value)


def _add_value(parent: ET.Element, tag: str, value: Any) -> None:
    if isinstance(value, list):
        for item in value:
            _add_value(parent, tag, item)
        return
    element = ET.SubElement(parent, tag)
    _fill_element(element, value)


def render_config(doc: dict) -> str:
    """Genera XML válido para pfSense 2.7 a partir de :func:`parse_config`."""
    if not isinstance(doc, dict):
        raise PfSenseError("el documento de configuración debe ser un diccionario")
    root = ET.Element("pfsense")
    _fill_element(root, doc)
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode", short_empty_elements=True)


def detect_ifnames(node: dict) -> dict:
    """Deduce WAN/LAN del tipo de adaptador QEMU usado por el nodo GNS3."""
    properties = node.get("properties", {}) if isinstance(node, dict) else {}
    adapter = str(properties.get("adapter_type", "")).lower()
    if adapter in ("e1000", "e1000e"):
        return {"wan": "em0", "lan": "em1"}
    if adapter.startswith("virtio"):
        return {"wan": "vtnet0", "lan": "vtnet1"}
    raise PfSenseError(f"adapter_type no soportado o ausente: {adapter or '(vacío)'}")


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value)


def _normalize_mask(mask: str) -> str:
    """Acepta máscara punteada o prefijo CIDR y devuelve la forma de config.xml."""
    text = str(mask).strip()
    try:
        return str(ipaddress.IPv4Address(text))
    except ipaddress.AddressValueError:
        pass
    try:
        prefix = int(text)
        if not 0 <= prefix <= 32:
            raise ValueError
        return str(ipaddress.IPv4Network(f"0.0.0.0/{prefix}").netmask)
    except ValueError as exc:
        raise PfSenseError(f"máscara IPv4 no válida: {mask}") from exc


def _parse_ifconfig(output: str) -> dict[str, dict[str, str]]:
    """Extrae nombres, IPv4 y máscaras de la salida FreeBSD de ``ifconfig``."""
    interfaces: dict[str, dict[str, str]] = {}
    current = None
    for line in output.splitlines():
        header = re.match(r"^([^\s:]+):\s", line)
        if header:
            current = header.group(1)
            interfaces[current] = {}
            continue
        address = re.search(r"\binet\s+(\S+)\s+netmask\s+(\S+)", line)
        if current and address:
            ip, mask = address.groups()
            try:
                mask = (str(ipaddress.IPv4Address(int(mask, 16)))
                        if mask.lower().startswith("0x") else _normalize_mask(mask))
            except (PfSenseError, ValueError):
                continue
            interfaces[current].update(ip=ip, mask=mask)
    return interfaces


def _insert_rule(container: dict, rule: dict) -> None:
    """Inserta antes del primer rechazo; el orden del array es el orden de evaluación."""
    existing = container.get("rule", [])
    rules = list(existing) if isinstance(existing, list) else ([] if existing == "" else [existing])
    position = len(rules)
    for index, item in enumerate(rules):
        action = item.get("type", item.get("action", "")) if isinstance(item, dict) else ""
        if str(action).lower() in ("reject", "block"):
            position = index
            break
    rules.insert(position, rule)
    container["rule"] = rules


def _endpoint(value: str) -> dict:
    text = str(value).strip()
    if text.lower() == "any":
        return {"any": ""}
    key = "network" if "/" in text else "address"
    return {key: text}


class PfSense:
    """Cliente SSH de pfSense. Los métodos de cambio vuelcan siempre por ``put_config``."""

    def __init__(self, host="192.168.1.1", user="admin", password=None,
                 port=22022, timeout=20):
        self.host = host
        self.user = user
        self.password = password
        self.port = int(port)
        self.timeout = float(timeout)

    @classmethod
    def from_env(cls) -> "PfSense":
        """Carga ``PFSENSE_HOST/USER/PASSWORD/PORT``; la contraseña es obligatoria."""
        password = os.environ.get("PFSENSE_PASSWORD")
        if not password:
            raise PfSenseError("falta la variable de entorno PFSENSE_PASSWORD")
        port = os.environ.get("PFSENSE_PORT") or "22022"
        try:
            return cls(host=os.environ.get("PFSENSE_HOST") or "192.168.1.1",
                       user=os.environ.get("PFSENSE_USER") or "admin",
                       password=password, port=port)
        except ValueError as exc:
            raise PfSenseError(f"PFSENSE_PORT no es un puerto válido: {port}") from exc

    def _redact(self, value: str | bytes | None) -> str:
        text = _as_text(value)
        return text.replace(self.password, "***") if self.password else text

    def run(self, cmd: str, timeout=None) -> dict:
        """Ejecuta un comando remoto y devuelve ``{cmd, output, ok, error}``."""
        if not self.password:
            return {"cmd": cmd, "output": "", "ok": False,
                    "error": "falta la variable de entorno PFSENSE_PASSWORD"}
        if not isinstance(cmd, str) or not cmd.strip():
            return {"cmd": cmd, "output": "", "ok": False, "error": "comando vacío"}
        try:
            effective_timeout = self.timeout if timeout is None else float(timeout)
            if effective_timeout <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return {"cmd": self._redact(cmd), "output": "", "ok": False,
                    "error": f"timeout no válido: {timeout}"}
        args = ["sshpass", "-p", self.password, "ssh", "-p", str(self.port),
                "-o", "StrictHostKeyChecking=no", f"{self.user}@{self.host}", cmd]
        try:
            completed = subprocess.run(args, capture_output=True, text=True,
                                       timeout=effective_timeout)
        except subprocess.TimeoutExpired as exc:
            detail = f"timeout tras {effective_timeout:g}s"
            stderr = self._redact(exc.stderr).strip()
            return {"cmd": self._redact(cmd), "output": self._redact(exc.stdout).rstrip("\n"),
                    "ok": False, "error": f"{detail}: {stderr}" if stderr else detail}
        except OSError as exc:
            return {"cmd": self._redact(cmd), "output": "", "ok": False,
                    "error": self._redact(str(exc))}

        output = self._redact(completed.stdout).rstrip("\n")
        stderr = self._redact(completed.stderr).strip()
        ok = completed.returncode == 0
        error = None if ok else (stderr or f"ssh terminó con código {completed.returncode}")
        return {"cmd": self._redact(cmd), "output": output, "ok": ok, "error": error}

    def status(self) -> dict:
        """Versión, interfaces, reglas y tabla de rutas del firewall."""
        commands = {
            "version": "cat /etc/version",
            "interfaces": "ifconfig",
            "rules": "pfctl -sr",
            "routes": "netstat -rn",
        }
        result: dict[str, Any] = {"ok": True}
        errors = []
        for key, command in commands.items():
            response = self.run(command)
            result[key] = response["output"] if response["ok"] else response["error"]
            if not response["ok"]:
                result["ok"] = False
                errors.append(f"{command}: {response['error']}")
        if errors:
            result["errors"] = errors
        return result

    def get_config(self) -> dict:
        """Lee y parsea ``/conf/config.xml``; devuelve el documento o un error."""
        response = self.run("cat /conf/config.xml")
        if not response["ok"]:
            return {"ok": False, "error": response["error"]}
        try:
            return parse_config(response["output"])
        except PfSenseError as exc:
            return {"ok": False, "error": str(exc)}

    def put_config(self, doc: dict, backup=True) -> dict:
        """Copia de seguridad, escritura atómica del XML y recarga de pfSense."""
        try:
            xml = render_config(doc)
        except PfSenseError as exc:
            return {"ok": False, "backup": None, "detail": str(exc)}
        backup_path = None
        if backup:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            backup_path = f"/conf/config.xml.bak-{stamp}"
            copied = self.run(f"cp -p /conf/config.xml {backup_path}")
            if not copied["ok"]:
                return {"ok": False, "backup": None, "detail": copied["error"]}

        encoded = base64.b64encode(xml.encode()).decode("ascii")
        temporary = "/conf/config.xml.tmp"
        chunk_size = 60000
        if len(encoded) > chunk_size:
            payload_path = "/conf/config.xml.b64"
            commands = [f"umask 077; : > {payload_path}"]
            commands.extend(
                f"umask 077; printf '%s' '{encoded[offset:offset + chunk_size]}' >> {payload_path}"
                for offset in range(0, len(encoded), chunk_size)
            )
            commands.append(f"umask 077; base64 -d {payload_path} > {temporary} "
                            f"&& mv {temporary} /conf/config.xml && rm -f {payload_path}")
        else:
            commands = [f"umask 077; printf '%s' '{encoded}' | base64 -d > {temporary} "
                        f"&& mv {temporary} /conf/config.xml"]
        for command in commands:
            write = self.run(command)
            if not write["ok"]:
                return {"ok": False, "backup": backup_path, "detail": write["error"]}
        reload_command = getattr(self, "_reload_command", "/etc/rc.reload_all")
        reloaded = self.run(reload_command)
        detail = reloaded["output"] if reloaded["ok"] else reloaded["error"]
        return {"ok": reloaded["ok"], "backup": backup_path,
                "detail": detail or "config.xml escrita y recargada"}

    def _load_and_save(self, change: Callable[[dict], None]) -> dict:
        doc = self.get_config()
        if doc.get("ok") is False:
            return {"ok": False, "backup": None, "detail": doc["error"]}
        change(doc)
        return self.put_config(doc)

    @staticmethod
    def _logical_interface(doc: dict, ifname: str) -> str | None:
        interfaces = doc.get("interfaces", {})
        if isinstance(interfaces, dict) and ifname in interfaces:
            return ifname
        if isinstance(interfaces, dict):
            for role, values in interfaces.items():
                if isinstance(values, dict) and values.get("if") == ifname:
                    return role
        return None

    def interfaces(self) -> dict:
        """Devuelve WAN/LAN/OPT con IP, máscara y si obtiene la IP por DHCP."""
        raw = self.run("ifconfig")
        if not raw["ok"]:
            return {"ok": False, "error": raw["error"]}
        doc = self.get_config()
        if doc.get("ok") is False:
            return {"ok": False, "error": doc["error"]}
        detected = _parse_ifconfig(raw["output"])
        configured = doc.get("interfaces") or {}
        if not isinstance(configured, dict):
            return {"ok": False, "error": "la sección <interfaces> no es un diccionario"}
        result = {}
        for role, values in configured.items():
            if role.startswith("@") or not isinstance(values, dict):
                continue
            ifname = str(values.get("if", ""))
            address = detected.get(ifname, {})
            configured_ip = str(values.get("ipaddr", ""))
            configured_mask = str(values.get("subnet", ""))
            try:
                mask = _normalize_mask(configured_mask) if configured_mask else ""
            except PfSenseError:
                mask = configured_mask
            dhcp = configured_ip.lower() == "dhcp"
            result[role] = {
                "if": ifname,
                "ip": address.get("ip", "" if dhcp else configured_ip),
                "mask": address.get("mask", mask),
                "dhcp": dhcp,
            }
        return result

    def assign(self, mapping: dict) -> dict:
        """Asigna nombres físicos a roles lógicos tras comprobar que existen."""
        if not isinstance(mapping, dict) or not mapping:
            return {"ok": False, "error": "mapping de interfaces vacío"}
        checked = self.run("ifconfig")
        if not checked["ok"]:
            return {"ok": False, "error": checked["error"]}
        available = list(_parse_ifconfig(checked["output"]))
        assigned = []
        for role, ifname in mapping.items():
            if role != "wan" and role != "lan" and not re.fullmatch(r"opt\d+", role):
                return {"ok": False, "error": f"rol de interfaz no válido: {role}"}
            if ifname is not None:
                if ifname not in available:
                    names = ", ".join(available) or "ninguna"
                    return {"ok": False, "error": f"la interfaz {ifname} no existe; disponibles: {names}",
                            "available": available}
                if ifname in assigned:
                    return {"ok": False, "error": f"la interfaz {ifname} ya está asignada"}
                assigned.append(ifname)

        def change(doc):
            interfaces = doc.get("interfaces")
            if not isinstance(interfaces, dict):
                interfaces = {}
                doc["interfaces"] = interfaces
            for role, ifname in mapping.items():
                if ifname is None:
                    interfaces.pop(role, None)
                else:
                    values = interfaces.get(role)
                    if not isinstance(values, dict):
                        values = {}
                        interfaces[role] = values
                    values["if"] = ifname

        return self._load_and_save(change)

    def set_ip(self, ifname, ip, mask, gateway=None) -> dict:
        """Configura IPv4 estática en la interfaz lógica asociada a ``ifname``."""
        try:
            address = str(ipaddress.IPv4Address(ip))
            netmask = _normalize_mask(mask)
            if gateway is not None:
                gateway = str(ipaddress.IPv4Address(gateway))
        except (ipaddress.AddressValueError, PfSenseError) as exc:
            return {"ok": False, "backup": None, "detail": str(exc)}

        def change(doc):
            role = self._logical_interface(doc, ifname)
            if role is None:
                raise PfSenseError(f"no hay interfaz lógica asignada a {ifname}")
            values = doc["interfaces"][role]
            if not isinstance(values, dict):
                values = {}
                doc["interfaces"][role] = values
            values["ipaddr"] = address
            values["subnet"] = netmask
            if gateway is not None:
                values["gateway"] = gateway

        try:
            return self._load_and_save(change)
        except PfSenseError as exc:
            return {"ok": False, "backup": None, "detail": str(exc)}

    def dhcp(self, ifname, start, end, dns=None) -> dict:
        """Activa el rango DHCP y, opcionalmente, los servidores DNS de una interfaz."""
        try:
            first, last = ipaddress.IPv4Address(start), ipaddress.IPv4Address(end)
            if first > last:
                raise PfSenseError("el inicio del rango DHCP es mayor que el final")
            dns_values = ([item for item in re.split(r"[,\s]+", dns) if item]
                          if isinstance(dns, str) else list(dns or []))
            for item in dns_values:
                ipaddress.IPv4Address(item)
        except (ipaddress.AddressValueError, PfSenseError) as exc:
            return {"ok": False, "backup": None, "detail": str(exc)}

        def change(doc):
            role = self._logical_interface(doc, ifname)
            if role is None:
                raise PfSenseError(f"no hay interfaz lógica asignada a {ifname}")
            dhcpd = doc.get("dhcpd")
            if not isinstance(dhcpd, dict):
                dhcpd = {}
                doc["dhcpd"] = dhcpd
            values = dhcpd.get(role)
            if not isinstance(values, dict):
                values = {}
                dhcpd[role] = values
            values["enable"] = ""
            values["range"] = {"from": str(first), "to": str(last)}
            if dns_values:
                values["dnsserver"] = dns_values[0] if len(dns_values) == 1 else dns_values

        try:
            return self._load_and_save(change)
        except PfSenseError as exc:
            return {"ok": False, "backup": None, "detail": str(exc)}

    def rule(self, action="pass", ifname="lan", proto="any", src="any",
             dst="any", port=None) -> dict:
        """Añade una regla de filtrado antes de cualquier rechazo existente."""
        action, proto = str(action).lower(), str(proto).lower()
        if action not in ("pass", "block", "reject"):
            return {"ok": False, "error": f"acción de filtro no válida: {action}"}
        if port is not None:
            try:
                number = int(port)
                if not 1 <= number <= 65535 or proto not in ("tcp", "udp"):
                    raise ValueError
            except ValueError:
                return {"ok": False, "error": "port requiere un puerto 1-65535 y proto tcp o udp"}

        def change(doc):
            role = self._logical_interface(doc, ifname)
            if role is None:
                raise PfSenseError(f"no hay interfaz lógica asignada a {ifname}")
            destination = _endpoint(dst)
            if port is not None:
                destination["port"] = str(port)
            rule = {"type": action, "interface": role, "ipprotocol": "inet",
                    "protocol": proto, "source": _endpoint(src), "destination": destination}
            filters = doc.setdefault("filter", {})
            if not isinstance(filters, dict):
                raise PfSenseError("la sección <filter> no es un diccionario")
            _insert_rule(filters, rule)

        try:
            return self._load_and_save(change)
        except PfSenseError as exc:
            return {"ok": False, "backup": None, "detail": str(exc)}

    def nat(self, ifname="wan", target=None) -> dict:
        """Configura NAT saliente automático o manual hacia ``target``."""
        if target is not None:
            try:
                target = str(ipaddress.IPv4Address(target))
            except ipaddress.AddressValueError as exc:
                return {"ok": False, "backup": None, "detail": f"target NAT no válido: {target}"}

        def change(doc):
            role = self._logical_interface(doc, ifname)
            if role is None:
                raise PfSenseError(f"no hay interfaz lógica asignada a {ifname}")
            nat = doc.get("nat")
            if not isinstance(nat, dict):
                nat = {}
                doc["nat"] = nat
            outbound = nat.get("outbound")
            if not isinstance(outbound, dict):
                outbound = {}
                nat["outbound"] = outbound
            outbound["mode"] = "manual" if target is not None else "automatic"
            rule = {"interface": role, "source": {"any": ""}, "destination": {"any": ""}}
            if target is not None:
                rule["target"] = target
            _insert_rule(outbound, rule)

        try:
            return self._load_and_save(change)
        except PfSenseError as exc:
            return {"ok": False, "backup": None, "detail": str(exc)}

    def enable_ssh(self, port=22022) -> dict:
        """Habilita SSH y fija su puerto en la sección ``system``."""
        try:
            number = int(port)
            if not 1 <= number <= 65535:
                raise ValueError
        except ValueError:
            return {"ok": False, "backup": None, "detail": f"puerto SSH no válido: {port}"}

        def change(doc):
            system = doc.get("system")
            if not isinstance(system, dict):
                system = {}
                doc["system"] = system
            ssh = system.get("ssh")
            if not isinstance(ssh, dict):
                ssh = {}
                system["ssh"] = ssh
            ssh["enable"] = "on"
            ssh["port"] = str(number)

        # La recarga y el arranque de sshd comparten sesión: si cambia el puerto,
        # no hace falta reconectar todavía al puerto antiguo.
        missing = object()
        previous = getattr(self, "_reload_command", missing)
        self._reload_command = "/etc/rc.reload_all && /etc/sshd"
        try:
            saved = self._load_and_save(change)
        finally:
            if previous is missing:
                self.__dict__.pop("_reload_command", None)
            else:
                self._reload_command = previous
        if not saved["ok"]:
            return saved
        self.port = number
        return saved
