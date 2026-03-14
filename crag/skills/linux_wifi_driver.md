+++
name = "Linux WiFi Driver Analysis"
description = "Strategies for tracing Linux kernel WiFi driver code paths"
keywords = ["wifi", "driver", "kernel", "linux", "802.11", "wlan", "pci", "usb", "mac80211", "cfg80211"]
project_types = ["c", "cpp"]
priority = 20
+++

### Linux Wi-Fi Driver Analysis Strategy

1. **TX/RX Separation**: Connection requests (TX path) often end at the hardware queue or DMA send function. You MUST stop tracing downwards there. Instead, search for the RX (Receive) Interrupt Handlers or Tasklets to find how the hardware response (e.g., Beacons, Auth frames) continues the state machine.

2. **Event Dispatchers**: Drivers wrap states in macros (e.g., MSG_EVT_*). If a function sets a state and returns, use `global_text_search` to find the switch-case consumer of that macro.

3. **Search Fallback SOP**: If `global_text_search` returns no matches when searching with a strict pattern like `*.c`, you MUST immediately think laterally and repeat the search using `*.[ch]` or no pattern at all. Macros, ENUMs, and external struct definitions are almost always in header files.

4. **Callback Discovery Pattern**: When a function initializes a struct (e.g., 'token', 'cmd', 'req') and passes it to a dispatcher or queue, you MUST look for assignments like 'struct->handler = func_name;'. Use `global_text_search` to find where the struct definition resides and check for all assigned function pointers. The real logic often resumes in the callback, not the dispatcher.

### Key Data Structures

- `ieee80211_hw`: Main hardware abstraction
- `ieee80211_vif`: Virtual interface (per-connection)
- `ieee80211_sta`: Station info (peer)
- `sk_buff`: Network packet buffer

### Common Entry Points

- `probe()`: Device initialization
- `start()`: Interface up
- `tx()`: Transmit path
- `rx()`: Receive interrupt handler
- `config()`: Configuration changes