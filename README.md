# LibrePush Glucose Monitor with Pushover Notifications

This project monitors glucose levels from FreeStyle Libre using `pylibrelinkup` and sends notifications through Pushover for critical glucose levels. Notifications are sent based on thresholds and include features such as priority levels and custom sounds.

## Prerequisites

- Python 3.7 or higher
- Pushover account and application API token
- FreeStyle LibreLinkUp account

## Setup Instructions

### 1. Clone the Repository

```bash
git clone git@github.com:karstennoe/LibrePush.git
cd libre_push_monitor
```

### 2. Create a Virtual Environment

Create a virtual environment to isolate the project dependencies:

```bash
python -m venv venv
```

Activate the virtual environment:

- On **Windows**:

  ```bash
  venv\Scripts\activate
  ```

- On **macOS/Linux**:

  ```bash
  source venv/bin/activate
  ```

### 3. Install Requirements

With the virtual environment activated, install the required packages:

```bash
pip install -r requirements.txt
```

### 4. Create a Configuration File

Copy the `config_example.json` file to `config.json`:

```bash
cp config_example.json config.json
```

Edit the `config.json` file to include your credentials:

```json
{
    "libre_email": "your_libre_email@example.com",
    "libre_password": "your_libre_password",
    "pushover_user_key": "your_pushover_user_key",
    "pushover_api_token": "your_pushover_api_token"
}
```

### 5. Run the Script

Run the main script to start monitoring glucose levels:

```bash
python libre_pushover.py
```

## Configuration Options

- **`libre_email`**: Your email address for LibreLinkUp.
- **`libre_password`**: Your password for LibreLinkUp.
- **`pushover_user_key`**: Your Pushover user key.
- **`pushover_api_token`**: Your Pushover application API token.

## Notes

- Ensure your `config.json` file is **not** included in version control (e.g., add it to `.gitignore`).
- The script uses a retry mechanism with exponential backoff to handle rate limiting issues with the LibreLinkUp API.
- Adjust the glucose thresholds and Pushover notification settings in the script as needed.
