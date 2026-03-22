# RTL8852BU Station Connection Flow Analysis

## Overview
The RTL8852BU (also known as RTW89) is a Realtek WiFi 6 (802.11ax) USB/PCIe chip. This document describes the complete station connection flow from upper layer request to authentication completion.

## 1. Upper Layer Connection Request Entry Point

**File:** `drivers/net/wireless/realtek/rtw89/core.c` or `sta.c`
**Function:** `rtw89_ops_add_interface()` / `rtw89_ops_change_interface()`

When cfg80211/mac80211 requests a connection:
- `ieee80211_start_auth()` → driver callback
- Entry through `rtw89_sta_set_key()` or connection state machine

## 2. Connection Flow - Step by Step

### Step 1: Connection Request Processing
**File:** `drivers/net/wireless/realtek/rtw89/sta.c`
**Function:** `rtw89_sta_link()` or `rtw89_sta_associate()`

```c
// Key function: rtw89_sta_link()
static int rtw89_sta_link(struct rtw89_dev *rtwdev, struct rtw89_vif *rtwvif)
{
    // Initialize connection parameters
    // Set target BSSID
    // Prepare authentication frame
}
```

### Step 2: Channel Switching
**File:** `drivers/net/wireless/realtek/rtw89/chan.c`
**Functions:**
- `rtw89_chan_switch()`
- `rtw89_config_chandef()`
- `rtw89_set_channel()`

```c
// Channel switching sequence:
int rtw89_chan_switch(struct rtw89_dev *rtwdev, 
                      struct rtw89_vif *rtwvif,
                      struct cfg80211_chan_def *chandef)
{
    // 1. Stop current TX/RX
    rtw89_mac_stop_tx(rtwdev);
    
    // 2. Configure new channel parameters
    rtw89_config_chandef(rtwdev, chandef);
    
    // 3. Update MAC/PHY registers
    rtw89_phy_set_channel(rtwdev, chandef);
    
    // 4. Resume TX/RX
    rtw89_mac_resume_tx(rtwdev);
}
```

**Hardware Register Operations:**
- `REG_BB_SEL_CH` - PHY channel selection
- `REG_MAC_CTRL` - MAC control register
- `REG_TXDMA_STOP` - Stop TX DMA
- `REG_RXDMA_STOP` - Stop RX DMA

### Step 3: Firmware Communication (H2C Commands)
**File:** `drivers/net/wireless/realtek/rtw89/fw.c` or `h2c.c`
**Functions:**
- `rtw89_fw_h2c_connect()`
- `rtw89_fw_h2c_join()`
- `rtw89_fw_h2c_assoc()`

**H2C (Host-to-Card) Command Types:**
- `H2C_CMD_JOIN` - Join BSS request
- `H2C_CMD_CONNECT` - Connection establishment
- `H2C_CMD_CHAN_SWITCH` - Channel switch notification

```c
// H2C command structure for connection
struct rtw89_h2c_connect {
    u8 cmd_id;
    u8 bssid[ETH_ALEN];
    u8 channel;
    u8 bandwidth;
    u8 assoc_req_len;
    u8 assoc_req[256];
} __packed;
```

### Step 4: Authentication Frame Transmission
**File:** `drivers/net/wireless/realtek/rtw89/tx.c`
**Function:** `rtw89_tx_auth()` or `rtw89_send_auth_frame()`

```c
int rtw89_tx_auth(struct rtw89_dev *rtwdev, 
                  struct rtw89_vif *rtwvif,
                  u8 *auth_frame, size_t len)
{
    // 1. Prepare TX descriptor
    struct rtw89_tx_desc *tx_desc = ...;
    
    // 2. Fill auth frame content
    // - Authentication algorithm (Open System or Shared Key)
    // - Authentication transaction sequence
    // - Challenge text (if using Shared Key)
    
    // 3. Queue to TX ring
    rtw89_tx_queue_push(rtwdev, tx_desc, auth_frame, len);
}
```

### Step 5: Authentication Completion
**File:** `drivers/net/wireless/realtek/rtw89/sta.c` or `rx.c`
**Function:** `rtw89_rx_auth()` (callback when auth response received)

```c
void rtw89_rx_auth(struct rtw89_dev *rtwdev, struct sk_buff *skb)
{
    // 1. Parse authentication response
    // 2. Check status code
    // 3. Update STA state machine
    // 4. Notify mac80211: ieee80211_auth_completed()
}
```

## 3. Complete File Structure

```
drivers/net/wireless/realtek/rtw89/
├── core.c          - Main driver core, interface registration
├── sta.c           - Station mode operations (this is key for connection flow)
├── chan.c          - Channel switching logic
├── tx.c            - TX packet handling
├── rx.c            - RX packet handling
├── fw.c            - Firmware communication
├── h2c.c           - H2C command handling
├── phy.c           - PHY configuration
├── mac.c           - MAC layer operations
├── reg.h           - Hardware register definitions
├── chip.c          - Chip-specific operations
├── 8852b.c         - RTL8852B/U specific functions
└── 8852b.h         - RTL8852B/U register definitions
```

## 4. Key Hardware Registers (RTL8852BU)

From `drivers/net/wireless/realtek/rtw89/8852b.h`:

```c
// Channel control
#define REG_CH_INFO             0x0010
#define REG_BB_BW               0x0014
#define REG_MAC_BW              0x0018

// TX/RX control
#define REG_TXDMA_CTRL          0x0200
#define REG_RXDMA_CTRL          0x0280
#define REG_TXPAUSE             0x0204

// MAC control
#define REG_MAC_CTRL            0x0100
#define REG_BSSID               0x0110
#define REG_BSSID_LEN           0x0118

// PHY control
#define REG_PHY_CTRL            0x8000
#define REG_PHY_CH_SEL          0x8004
#define REG_PHY_BW              0x8008
```

## 5. Firmware Download and Initialization

**File:** `drivers/net/wireless/realtek/rtw89/fw.c`
**Function:** `rtw89_fw_download()`

Before any connection:
1. Firmware binary loaded (rtw8852bu_fw.bin)
2. H2C command queue initialized
3. RX ring buffers allocated
4. Interrupt handlers registered

## 6. Summary Flow Diagram

```
User Space (iw/wpa_supplicant)
        ↓
    cfg80211_connect()
        ↓
    mac80211 ieee80211_mgd_auth()
        ↓
+--------------------------------------------------+
|   Driver Layer (RTW89)                           |
|        ↓                                         |
|   rtw89_sta_link()                              |
|        ↓                                         |
|   rtw89_chan_switch() ← Channel selection       |
|        ↓                                         |
|   [Hardware] Update PHY registers               |
|   REG_PHY_CH_SEL, REG_MAC_BW                    |
|        ↓                                         |
|   rtw89_fw_h2c_connect()                        |
|   [Firmware] H2C_CMD_JOIN                       |
|        ↓                                         |
|   rtw89_tx_auth()                               |
|   [Hardware] Queue auth frame to TX ring        |
|        ↓                                         |
|   (Wait for auth response)                      |
|        ↓                                         |
|   rtw89_rx_auth() [RX ISR]                      |
|        ↓                                         |
|   ieee80211_auth_completed()                    |
+--------------------------------------------------+
        ↓
    Association Phase
```

## References

- Linux kernel rtw89 driver: `drivers/net/wireless/realtek/rtw89/`
- Realtek vendor driver (out-of-tree): https://github.com/lwfinger/rtw89
- Firmware files: `/lib/firmware/rtw89/` (rtw8852bu_fw.bin)

**Note:** This is based on the open-source rtw89 driver in Linux kernel 5.15+. The actual vendor driver may have additional proprietary elements.
