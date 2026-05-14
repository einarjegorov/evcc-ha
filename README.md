<img width="400" height="400" alt="logo_qg8JSfs-overlay" src="https://github.com/user-attachments/assets/427496a4-4033-4b9a-ba56-bf63c3a7975f" />

# EVCC integration for Home Assistant

`evcc-ha` is a thin custom integration for exposing EVCC loadpoints to Home
Assistant.

The integration connects to EVCC at:

- `GET http://<host>:7070/api/state` for setup and recovery snapshots
- `ws://<host>:7070/ws` for live updates
- `POST /api/loadpoints/<id>/mode/<mode>` for mode buttons

## Features

- UI setup through a Home Assistant config flow
- One Home Assistant device per EVCC loadpoint
- Loadpoint connection, charging, power, session energy, cumulative energy, mode,
  and vehicle sensors
- Dedicated buttons for `off`, `now`, `minpv`, and `pv`
- Persistent cumulative energy that survives EVCC session resets
- Minute heartbeat for charge power and cumulative energy history generation

## Installation

1. Add this repository to HACS as a custom repository of type `Integration`.
2. Install `EVCC`.
3. Restart Home Assistant.
4. Add the `EVCC` integration from `Settings -> Devices & services`.
5. Enter the EVCC host and port.

## Security Notes

This integration assumes EVCC is reachable on a trusted LAN. Do not expose an
unencrypted EVCC instance directly to the internet.

## AI Disclosure

AI-assisted tools were used during the development of this integration.

## Entity List Showcase

<img width="392" height="885" alt="image" src="https://github.com/user-attachments/assets/243a081c-bf4b-46db-86bd-6deaa31f3c01" />
