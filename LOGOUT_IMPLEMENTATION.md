# Logout Implementation & User Data Reset Analysis
## ND Data Importer QGIS Plugin

---

## 1. LOGOUT SIGNAL HANDLING & CONNECTION

### Where logout_requested Signal is Handled:

**File:** `/Users/itachi/Documents/Github/NeedleDigital/platform-qgis-plugin/src/ui/main_dialog.py`
- **Line 60:** Signal definition: `logout_requested = pyqtSignal()`
- **Lines 730-735:** User-initiated logout handler:
  ```python
  def _handle_login_button(self):
      """Handle login/logout button click."""
      if self.login_button.text() == "Login":
          self.login_requested.emit()
      else:
          self.logout_requested.emit()
  ```

**File:** `/Users/itachi/Documents/Github/NeedleDigital/platform-qgis-plugin/data_importer.py`
- **Line 225:** Signal connection: `self.dlg.logout_requested.connect(self._handle_logout_request)`
- **Lines 281-302:** Main logout handler

---

## 2. LOGOUT IMPLEMENTATION (BOTH USER-INITIATED & TOKEN REFRESH)

### User-Initiated Logout:
**File:** `/Users/itachi/Documents/Github/NeedleDigital/platform-qgis-plugin/data_importer.py`
**Lines 281-302:**

```python
def _handle_logout_request(self):
    """Handle logout request from dialog."""
    try:
        # Check if user was actually authenticated before logout
        was_authenticated = self.data_manager.api_client.is_authenticated()

        self.data_manager.api_client.logout()
        self.dlg.update_login_status(False)

        # Clear any existing data
        self.dlg.show_data("Holes", [], [], {...})
        self.dlg.show_data("Assays", [], [], {...})

        # Only show logout success message if user was actually logged in
        if was_authenticated and self.dlg:
            self.dlg.show_plugin_message("Logged out successfully", "info", 3000)
```

### Programmatic Token Refresh Logout:
**File:** `/Users/itachi/Documents/Github/NeedleDigital/platform-qgis-plugin/data_importer.py`
**Lines 365-375:**

```python
def _validate_token_and_logout_if_expired(self):
    """Validate token and automatically logout if expired."""
    try:
        if not self.data_manager.is_authenticated():
            # Token is expired or invalid, logout user
            self._handle_logout_request()
            # Show message about session expiration
            if self.dlg:
                self.dlg.show_plugin_message("Session expired. Please log in again.", "warning", 4000)
```

**Trigger Point:** 
- Called when dialog is shown/raised (Line 1391 in main_dialog.py): `self.validate_token_on_show()`
- Token validation happens on `show_and_raise()` method

### Login Required Logout (Auto-logout before login):
**File:** `/Users/itachi/Documents/Github/NeedleDigital/platform-qgis-plugin/data_importer.py`
**Lines 377-388:**

```python
def _handle_login_required(self):
    """Handle login required signal - show login dialog directly."""
    try:
        # Ensure user is logged out first
        self._handle_logout_request()
        # Show login dialog directly without error message
        if not self.login_dlg:
            self.login_dlg = LoginDialog(self.dlg, self.data_manager.api_client)
            self.login_dlg.login_attempt.connect(self._handle_login_attempt)
        self.login_dlg.exec_()
```

---

## 3. API CLIENT LOGOUT (TOKEN CLEARING)

**File:** `/Users/itachi/Documents/Github/NeedleDigital/platform-qgis-plugin/src/api/client.py`
**Lines 195-212:**

```python
def logout(self) -> None:
    """Logout user and clear stored tokens."""
    self.auth_token = None
    self.refresh_token = None
    self.token_expires_at = 0
    self.user_role = None
    self.last_login_email = ""
    self.token_refresh_timer.stop()

    # Clear all stored tokens, expiration time, and email
    settings = QgsSettings()
    settings.remove("needle/refreshToken")
    settings.remove("needle/authToken")
    settings.remove("needle/tokenExpiresAt")
    settings.remove("needle/lastLoginEmail")

    # Cancel any ongoing requests
    self.cancel_all_requests()
```

**Key Actions:**
1. Clears in-memory tokens (auth_token, refresh_token)
2. Clears token expiration time
3. Clears user role info
4. Clears last login email
5. Stops token refresh timer
6. Removes all persisted tokens from QGIS settings
7. Cancels all active network requests

---

## 4. ALL USER-SPECIFIC DATA THAT NEEDS RESET ON LOGOUT

### A. AUTHENTICATION & TOKEN DATA
**Location:** `ApiClient` class in `/Users/itachi/Documents/Github/NeedleDigital/platform-qgis-plugin/src/api/client.py`

| Data Item | Storage | Cleared Method | Lines |
|-----------|---------|-----------------|-------|
| `auth_token` | In-memory + QgsSettings | `logout()` | 197, 207 |
| `refresh_token` | In-memory + QgsSettings | `logout()` | 198, 206 |
| `token_expires_at` | In-memory + QgsSettings | `logout()` | 199, 208 |
| `user_role` | In-memory (extracted from token) | `logout()` | 200 |
| `last_login_email` | In-memory + QgsSettings | `logout()` | 201, 209 |
| Token refresh timer | QTimer state | `logout()` | 202 |
| Active network requests | `_active_replies` list | `cancel_all_requests()` | 212 |

**QgsSettings Keys Cleared:**
- `needle/refreshToken`
- `needle/authToken`
- `needle/tokenExpiresAt`
- `needle/lastLoginEmail`

---

### B. TAB DATA STATE

**Location:** `DataManager` class in `/Users/itachi/Documents/Github/NeedleDigital/platform-qgis-plugin/src/core/data_manager.py`
**Lines 412-444:** Data clearing methods

**Currently NOT automatically cleared on logout** - Only manually cleared via Reset All button or data clear requests.

#### Tab State Structure:
```python
self.tab_states = {
    'Holes': {
        'data': [],                    # Full dataset for QGIS import
        'display_data': [],            # First 1K records (for fast table pagination)
        'headers': [],                 # Column headers
        'total_records': 0,           # Total count from API
        'current_page': 0,            # Current pagination page (0-based)
        'records_per_page': 100,      # Records per page in table
        'filter_params': {},          # Last used filter parameters
        'fetch_details': {}           # Last fetch details for View Details dialog
    },
    'Assays': { ... }  # Same structure
}
```

#### Clearing Methods:
1. **`clear_tab_data(tab_name)`** (Lines 412-421):
   - Clears all data AND filter_params
   - Emits UI reset signals
   - Shows "Waiting for data..." message

2. **`_clear_tab_data(tab_name)`** (Lines 423-433):
   - Internal method that clears everything
   - Used by `clear_tab_data()`

3. **`_clear_tab_data_only(tab_name)`** (Lines 435-444):
   - Clears data but preserves filter_params
   - Used during new fetch to keep filters intact

---

### C. FILTER STATE & DIALOG DATA

**Location:** `/Users/itachi/Documents/Github/NeedleDigital/platform-qgis-plugin/src/ui/main_dialog.py`

#### Filter Widgets Created:

**Holes Tab:**
- `state_filter` (StaticFilterWidget) - Line 200
- `hole_type_filter` (SearchableStaticFilterWidget) - Line 207
- `company_filter` (DynamicSearchFilterWidget) - Line 221
- `max_depth_input` (QLineEdit) - Line 250
- `count_input` (QLineEdit) - Line 291
- `bbox_button` (QPushButton) - Line 298
- `bbox_indicator` (QLabel) - Line 307
- `bbox_clear_button` (QPushButton) - Line 314
- `selected_bbox` (polygon dict or None) - Line 339

**Assays Tab:**
- `state_filter` (StaticFilterWidget) - Line 200
- `hole_type_filter` (SearchableStaticFilterWidget) - Line 207
- `element_input` (QComboBox) - Line 351
- `operator_input` (QComboBox) - Line 355
- `value_input` (QLineEdit) - Line 360
- `from_depth_input` (QLineEdit) - Line 454
- `to_depth_input` (QLineEdit) - Line 467
- `company_filter` (DynamicSearchFilterWidget) - Line 478
- `count_input` (QLineEdit) - Line 489
- `bbox_button`, `bbox_indicator`, `bbox_clear_button` - Lines 496-520
- `selected_bbox` (polygon dict or None) - Line 537

#### Filter Reset Method:
**File:** `/Users/itachi/Documents/Github/NeedleDigital/platform-qgis-plugin/src/ui/main_dialog.py`
**Lines 1536-1598:** `_reset_all_filters()`

Resets:
- State filter to "All States"
- Hole type filter (clear search box & selections)
- Company filter (clear search box & selections)
- Max depth input (for Holes)
- Depth range inputs (for Assays)
- Element selector (reset to first item)
- Operator selector (reset to "None")
- Value input (clear and disable)
- Record count (reset to 100)
- Bounding box selection (clear polygon)

**Filter Widget Internal State:**

1. **DynamicSearchFilterWidget** (Lines 449-613):
   - `_selected_items` dict: {data: text} of selected companies
   - `search_box` QLineEdit: Search text
   - Chip display: Visual representation of selections
   - Popup with results list

2. **SearchableStaticFilterWidget** (Lines 615-807):
   - `_selected_items` dict: Selected items
   - `search_box` QLineEdit: Search text
   - `_static_data` list: Available options
   - Chip display

3. **StaticFilterWidget** (Lines 808-...):
   - Checkable combo box with internal selection state
   - `_selected_data` list: Selected values

---

### D. TABLE & DISPLAY DATA

**Location:** `/Users/itachi/Documents/Github/NeedleDigital/platform-qgis-plugin/src/ui/main_dialog.py`

#### Table Widgets:
```python
'table': QTableWidget()  # Line 553
'loading_label': QLabel()  # Line 562
'no_data_label': QLabel()  # Line 569
'location_widget': QWidget()  # Line 577
'content_stack': QStackedLayout()  # Line 550
```

#### Clearing Table on Logout:
**File:** `/Users/itachi/Documents/Github/NeedleDigital/platform-qgis-plugin/data_importer.py`
**Lines 290-292:**
```python
# Clear any existing data
self.dlg.show_data("Holes", [], [], {'has_data': False, ...})
self.dlg.show_data("Assays", [], [], {'has_data': False, ...})
```

This triggers `show_data()` method (main_dialog.py lines 1192-1323) which:
1. Sets table row count to 0
2. Clears all table data
3. Shows "Waiting for data..." message
4. Hides import button
5. Hides pagination controls

---

### E. UI STATE CHANGES

**File:** `/Users/itachi/Documents/Github/NeedleDigital/platform-qgis-plugin/src/ui/main_dialog.py`
**Lines 1160-1178:** `update_login_status()` method

```python
def update_login_status(self, is_logged_in: bool, user_info: str = ""):
    """Update UI based on login status."""
    if is_logged_in:
        self.login_button.setText("Logout")
        self.reset_all_button.setVisible(True)
        # ... update status message and role badge
    else:
        self.login_button.setText("Login")
        self.reset_all_button.setVisible(False)
        self.status_label.setText(...)
        self.role_badge.setVisible(False)  # Hide role badge after logout
```

**On Logout:**
1. Login button text changes to "Login"
2. Reset All button becomes hidden
3. Role badge becomes hidden
4. Status message updates to ready state

---

### F. STREAMING & REQUEST STATE

**Location:** `/Users/itachi/Documents/Github/NeedleDigital/platform-qgis-plugin/src/core/data_manager.py`

| State Item | Lines | Cleared |
|------------|-------|---------|
| `streaming_state` dict | 121 | In `cancel_all_requests()` |
| `_is_fetching` flag | 123 | In `cancel_all_requests()` |
| `fetch_start_time` | 122 | On next fetch |
| `_active_replies` list | 98 (ApiClient) | In `cancel_all_requests()` |

**Note:** These are NOT explicitly cleared on logout but are safe states.

---

### G. COMPANY SEARCH STATE

**Location:** `/Users/itachi/Documents/Github/NeedleDigital/platform-qgis-plugin/src/ui/main_dialog.py`

| State Item | Lines |
|------------|-------|
| `company_search_timer` | 81 |
| `_current_company_query` | 84 |

**Not explicitly reset on logout** - Safe to leave (will require re-authentication for next search).

---

## 5. FILTER COMPONENT STRUCTURE

### DynamicSearchFilterWidget (Company Search)
**Location:** Lines 449-613 in components.py

**Features:**
- Live API-based company search
- Selected items stored as chips
- Maximum 4 visible chips + "view all" button
- Popup results list
- `_selected_items` dict: {company_id: company_name}
- `search_box` QLineEdit for typing search
- Emits `textChanged()` signal for debounced API calls

**Reset Required:**
- `_selected_items` dictionary
- `search_box` text
- Popup visibility

---

### StaticFilterWidget (State Selection)
**Location:** Lines 808+

**Features:**
- Checkable combo box
- Multiple selection support
- "All States" logic (selecting All unchecks individual states)
- `_selected_data` list of selected values

**Reset Required:**
- Set to [""] (All States)
- Uncheck all items

---

### SearchableStaticFilterWidget (Hole Type Filter)
**Location:** Lines 615-807

**Features:**
- Client-side search on static data
- Chip display for selections
- Search box filtering
- `_selected_items` dict
- `_static_data` list of options

**Reset Required:**
- Clear `_selected_items`
- Clear search_box
- Update chip display

---

## 6. TABLE WIDGET DATA MODEL

**Location:** `/Users/itachi/Documents/Github/NeedleDigital/platform-qgis-plugin/src/ui/main_dialog.py`
**Lines 553-615:**

```python
# Data table
table = QTableWidget()
table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
table.setEditTriggers(QTableWidget.NoEditTriggers)  # Read-only

# Loading label
loading_label = QLabel("Waiting for data...")

# No data label  
no_data_label = QLabel("No data present with given filters.")

# Stacked layout for switching between views
content_stack = QStackedLayout()
content_stack.addWidget(table)
content_stack.addWidget(loading_label)
content_stack.addWidget(no_data_label)
content_stack.addWidget(location_widget)
```

**On Logout - Table Clearing:**
1. `show_data()` called with empty data list
2. `table.setRowCount(0)` - Clear rows
3. `table.setColumnCount(0)` - Clear columns
4. `content_stack.setCurrentWidget(loading_label)` - Show "Waiting" message
5. Import button hidden
6. Pagination controls hidden
7. View Details button hidden

---

## 7. PAGINATION STATE

**Location:** `/Users/itachi/Documents/Github/NeedleDigital/platform-qgis-plugin/src/ui/main_dialog.py`

```python
'current_page': 0              # 0-based index
'records_per_page': 100        # Table rows per page
'total_pages': 0               # Calculated from data
'total_records': 0             # Total fetched from API
'display_count': 0             # Limited to MAX_DISPLAY_RECORDS (1000)
```

**On Logout:** 
- Pagination info emitted with all zeros
- `prev_button` and `next_button` become disabled
- `page_label` updates to "Page 0 of 0"

---

## 8. COMPLETE LOGOUT FLOW DIAGRAM

```
User clicks Logout Button
    ↓
_handle_login_button() emits logout_requested signal
    ↓
_handle_logout_request() in DataImporter
    ├─ Check if was authenticated
    ├─ Call api_client.logout()
    │   ├─ Clear auth_token, refresh_token, token_expires_at, user_role, last_login_email
    │   ├─ Stop token refresh timer
    │   ├─ Remove from QgsSettings (needle/*)
    │   └─ Cancel all active requests
    │
    ├─ Call dlg.update_login_status(False)
    │   ├─ Change button text to "Login"
    │   ├─ Hide Reset All button
    │   ├─ Hide role badge
    │   └─ Update status message
    │
    ├─ Call dlg.show_data("Holes", [], [], ...)
    │   ├─ Clear table rows/columns
    │   ├─ Show "Waiting for data..." message
    │   └─ Hide import/pagination buttons
    │
    ├─ Call dlg.show_data("Assays", [], [], ...)
    │   ├─ Clear table rows/columns
    │   ├─ Show "Waiting for data..." message
    │   └─ Hide import/pagination buttons
    │
    └─ Show "Logged out successfully" message (if was authenticated)
```

---

## 9. MISSING RESET POINTS (NOT CURRENTLY CLEARED ON LOGOUT)

The following filter states persist after logout and are NOT automatically reset:

1. **Filter Values in DataManager:**
   - `tab_states[tab_name]['filter_params']` - Not cleared on logout
   - **Impact:** If user logs back in with different account, previous filter params are still in memory

2. **Filter UI Input Values:**
   - The actual QLineEdit text values in filter widgets are NOT reset
   - **Impact:** Search boxes still contain previous search text
   - **However:** This is a UI concern only - data can't be fetched without login

3. **Bounding Box Selection:**
   - `tab_widgets['selected_bbox']` for Holes and Assays
   - **Impact:** Polygon selection persists between sessions
   - **Should be cleared:** In `_reset_all_filters()` but NOT on automatic logout

4. **Company Search Results:**
   - Results popup is cleared but search query remains
   - **Should be cleared:** In `_reset_all_filters()` or on logout

---

## 10. RECOMMENDATIONS FOR COMPLETE LOGOUT CLEANUP

To ensure complete user data isolation on logout, consider calling `_reset_all_filters()` in addition to current logout:

**Current Flow:**
```python
def _handle_logout_request(self):
    # ... current code ...
    self.data_manager.api_client.logout()
    self.dlg.update_login_status(False)
    # ... show_data calls ...
```

**Recommended Enhanced Flow:**
```python
def _handle_logout_request(self):
    # ... current code ...
    self.data_manager.api_client.logout()
    self.dlg.update_login_status(False)
    self.dlg._reset_all_filters()  # Add this to clear UI state
    # ... show_data calls ...
```

**Also Consider Clearing:**
1. `clear_tab_data()` for both tabs to clear DataManager state
2. Setting `display_data` to empty in DataManager (not just UI)

---

## 11. QgsSettings PERSISTENCE

All tokens stored in QgsSettings are cleared on logout:

```python
settings.remove("needle/refreshToken")      # Refresh token
settings.remove("needle/authToken")         # Access/ID token
settings.remove("needle/tokenExpiresAt")    # Token expiration timestamp
settings.remove("needle/lastLoginEmail")    # Email for autofill
```

**Note:** These are QGIS's encrypted settings storage - safe for token persistence.

---

## 12. STREAMING & ACTIVE REQUESTS

**Handled in logout:**
```python
# In api_client.logout()
self.cancel_all_requests()  # Aborts all active network requests
```

**Clears:**
- `_active_replies` list
- `_streaming_buffers` dict (if any)
- `_streaming_decompressors` dict (if any)
- `_streaming_text_buffers` dict (if any)

---

## SUMMARY TABLE

| Category | Location | Cleared | Method | Complete |
|----------|----------|---------|--------|----------|
| Auth Tokens | ApiClient | ✓ | logout() | Yes |
| Token Timer | ApiClient | ✓ | logout() | Yes |
| Active Requests | ApiClient | ✓ | cancel_all_requests() | Yes |
| Tab Data | DataManager | ✗ | Manual via show_data() | Partial |
| Tab Filter Params | DataManager | ✗ | Manual via _clear_tab_data() | No |
| Table UI | MainDialog | ✓ | show_data() | Yes |
| Filter Values (UI) | MainDialog | ✗ | Manual via _reset_all_filters() | No |
| Filter State (DictS) | Components | ✗ | Not called | No |
| Bounding Box | MainDialog | ✗ | Manual clear | No |
| Company Search | MainDialog | ✗ | Not cleared | No |
| Role Badge | MainDialog | ✓ | update_login_status() | Yes |
| Button States | MainDialog | ✓ | update_login_status() | Yes |
