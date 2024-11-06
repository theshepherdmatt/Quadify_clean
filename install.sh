#!/bin/bash
set -e

# ============================
#   Color Code Definitions
# ============================
RED='\033[0;31m'        # Red
GREEN='\033[0;32m'      # Green
YELLOW='\033[1;33m'     # Yellow
BLUE='\033[0;34m'       # Blue
CYAN='\033[0;36m'       # Cyan
MAGENTA='\033[0;35m'    # Magenta
NC='\033[0m'            # No Color

# ============================
#   Log File Definition
# ============================
LOG_FILE="/home/volumio/Quadify/install_details.log"

# ============================
#   Log Message Function
# ============================
log_message() {
    local type="$1"
    local message="$2"
    case "$type" in
        "info") echo -e "${BLUE}[INFO]${NC} $message" ;;
        "success") echo -e "${GREEN}[SUCCESS]${NC} $message" ;;
        "warning") echo -e "${YELLOW}[WARNING]${NC} $message" ;;
        "error") echo -e "${RED}[ERROR]${NC} $message" >&2 ;;
        "highlight") echo -e "${MAGENTA}$message${NC}" ;;
        *) echo -e "[UNKNOWN] $message" ;;
    esac
}

# ============================
#   ASCII Art Banner Function
# ============================
banner() {
    echo -e "${MAGENTA}"
    echo "  ___  _   _   _    ____ ___ _______   __"
    echo " / _ \| | | | / \  |  _ \_ _|  ___\ \ / /"
    echo "| | | | | | |/ _ \ | | | | || |_   \ V / "
    echo "| |_| | |_| / ___ \| |_| | ||  _|   | |  "
    echo " \__\_\\___/_/   \_\____/___|_|     |_|  "
    echo -e "${NC}"
}

# ============================
#   Spinner Function
# ============================
spinner() {
    local pid=$1
    local delay=0.1
    local spinstr='|/-\'
    while [ "$(ps a | awk '{print $1}' | grep $pid)" ]; do
        local temp=${spinstr#?}
        printf " [%c]  " "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
    printf "    \b\b\b\b"
}

# ============================
#   Prompt User Function
# ============================
prompt_user() {
    local message="$1"
    local response
    while true; do
        read -rp "$(echo -e "${CYAN}$message [y/n]: ${NC}")" response
        case "$response" in
            [Yy]* ) return 0;;
            [Nn]* ) return 1;;
            * ) echo -e "${YELLOW}Please answer yes or no.${NC}";;
        esac
    done
}

# ============================
#   Check for Root Privileges
# ============================
check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_message "warning" "Please run as root or use sudo."
        exit 1
    fi
}

# ============================
#   Install Python and pip
# ============================
install_python() {
    log_message "info" "Installing Python3 and pip..."
    apt update && apt install -y python3 python3-pip python3-smbus
}

# ============================
#   Install Python Packages
# ============================
install_dependencies() {
    log_message "info" "Installing required Python libraries..."
    pip3 install luma.oled Pillow requests socketIO-client-nexus
}

# ============================
#   Configure SPI and I2C
# ============================
configure_spi_i2c() {
    log_message "info" "Configuring SPI and I2C interfaces..."
    echo "dtparam=spi=on" | tee -a /boot/userconfig.txt > /dev/null
    echo "spi-dev" | tee -a /etc/modules > /dev/null
    echo "dtparam=i2c_arm=on" | tee -a /boot/userconfig.txt > /dev/null
    echo "i2c-dev" | tee -a /etc/modules > /dev/null
    log_message "info" "Reloading configurations. Reboot is recommended after installation."
}


# ============================
#   Verify I2C Devices
# ============================

verify_i2c() {
    log_message "info" "Verifying I2C configuration and detecting devices..."
    
    # Detect I2C devices on bus 1
    sudo i2cdetect -y 1 | tee -a "$LOG_FILE"
    
    # Check if any devices are detected
    DEVICE_COUNT=$(sudo i2cdetect -y 1 | grep -E '^[0-9a-fA-F]' | grep -v '--' | wc -l)
    
    if [ "$DEVICE_COUNT" -gt 0 ]; then
        log_message "success" "I2C devices detected successfully."
    else
        log_message "warning" "No I2C devices detected. Please check your connections and device addresses."
    fi
}

# ============================
#   Setup Main Service
# ============================

setup_main_service() {
    log_message "info" "Setting up the Main Quadify Service..."

    # Create the systemd service file
    tee /etc/systemd/system/quadify_main.service > /dev/null <<EOL
[Unit]
Description=Quadify Main Service
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/volumio/Quadify/main.py
Restart=always
User=volumio
WorkingDirectory=/home/volumio/Quadify
Environment=PATH=/usr/bin:/usr/local/bin
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOL

    # Reload systemd to apply the new service
    systemctl daemon-reload

    # Enable the service to start on boot
    systemctl enable quadify_main.service >> "$LOG_FILE" 2>&1 &

    # Start the service immediately
    systemctl start quadify_main.service >> "$LOG_FILE" 2>&1 &
    
    log_message "success" "Main Quadify Service has been created, enabled, and started."
}

# Call the function within your main installation sequence
setup_main_service


# ============================
#   Main Installation Function
# ============================
main() {
    # Display the ASCII Art Banner
    banner

    # Check for root privileges
    check_root

    # Install dependencies
    install_python
    install_dependencies

    # Configure SPI and I2C
    configure_spi_i2c

    # Final success message
    log_message "success" "Installation complete. Please reboot to apply hardware settings."
}

# Execute the main function
main
