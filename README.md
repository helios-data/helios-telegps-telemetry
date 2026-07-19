# helios-aprs-telemetry

Helios node for receiving and decoding APRS packets from a COTS GPS.

It runs Direwolf (software TNC) to demodulate audio into KISS frames, then decodes
those AX.25 frames into APRS fields and publishes them to Helios.

## Configuration

Everything is configured through **CLI arguments** (passed to `main.py`) or
**environment variables**. CLI arguments take priority over environment variables.

### CLI arguments

| Argument            | Env var           | Default                   | Description                                     |
| ------------------- | ----------------- | ------------------------- | ----------------------------------------------- |
| `--kiss-host HOST`  | `KISS_HOST`       | `localhost`               | Direwolf KISS TCP host                          |
| `--kiss-port PORT`  | `KISS_PORT`       | `8001`                    | Direwolf KISS TCP port                          |
| `-v`, `--verbose`   | —                 | off                       | Print all packet fields (default: one-liner)    |
| `-d`, `--debug`     | —                 | off                       | Hex-dump AX.25 bytes and TNC2 string to stderr  |
| `-o FILE`, `--output FILE` | `CSV_OUTPUT_PATH` | none (no logging) | Write decoded packets to a CSV log file         |

### Environment-only settings

These affect Direwolf startup and the Helios connection, and have no CLI flag:

| Env var           | Default                  | Description                                            |
| ----------------- | ------------------------ | ------------------------------------------------------ |
| `AUDIO_DEVICE`    | `auto`                   | ALSA capture device (e.g. `hw:1,0`). `auto` detects it |
| `MYCALL`          | `N0CALL`                 | Your station callsign, written into the Direwolf config |
| `HELIOS_NODE_URI` | `Helios.Services.TeleGPS`| Helios node URI to publish events to                   |

---

## Running with `run.sh`

`run.sh` auto-detects the audio device, starts Direwolf, waits for the KISS port,
then launches the decoder. Any arguments you pass are forwarded to `main.py`.

```bash
# Simplest run — auto-detect audio, defaults for everything else
./run.sh

# Set your callsign, print all fields, and log to CSV
MYCALL=VE7OKT ./run.sh --verbose --output packets.csv

# Pin a specific audio device and enable debug hex-dumps
AUDIO_DEVICE=hw:1,0 ./run.sh --debug

# Custom KISS host/port
./run.sh --kiss-host 127.0.0.1 --kiss-port 8001
```

---

## Running with Docker

Set config via `-e` environment variables. Any arguments after the image name are
forwarded to `main.py`. The container needs access to the sound card (`--device`).

```bash
# Build
docker build -t helios-aprs .

# Basic run — auto-detect audio, pass in your callsign
docker run --rm \
  --device /dev/snd \
  -e MYCALL=VE7OKT \
  helios-aprs

# Verbose output + CSV logging (mount a volume so the log persists)
docker run --rm \
  --device /dev/snd \
  -e MYCALL=VE7OKT \
  -v "$(pwd)/logs:/data" \
  helios-aprs --verbose --output /data/packets.csv

# Pin a specific audio device and set the Helios node URI
docker run --rm \
  --device /dev/snd \
  -e MYCALL=VE7OKT \
  -e AUDIO_DEVICE=hw:1,0 \
  -e HELIOS_NODE_URI=Helios.Services.TeleGPS \
  helios-aprs --debug
```

> **Note:** `--device /dev/snd` is required so the container can reach the sound
> card for audio capture.
