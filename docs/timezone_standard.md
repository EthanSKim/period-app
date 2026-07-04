# Date & Timezone Handling Standardization Policy

## 1. Overview and Core Strategy

In tracking applications (such as menstrual cycle trackers), date boundaries correspond to the user's local calendar day. They are not absolute UTC timestamps. If a user logs a period starting on **June 20, 2026**, they expect it to be recorded as June 20, 2026, regardless of where they are in the world, what timezone their browser is currently set to, or the timezone of the server.

To prevent off-by-one date errors and timezone shift bugs, this project enforces the following rule:

> [!IMPORTANT]
> **Use Timezone-Naive Calendar Dates (YYYY-MM-DD) for all cycle and period dates.**
> Absolutely no timezone conversion, time-of-day offsets, or UTC shifts are allowed for cycle start and end dates.

---

## 2. Technical Stack Specifications

### 2.1 Database (PostgreSQL)
* **Column Type**: Cycle start and end dates must use the database `DATE` column type (e.g., `start_date DATE NOT NULL`).
* **Why**: The SQL `DATE` type stores only year, month, and day without timezone or time-of-day information. 

### 2.2 Backend (FastAPI / SQLAlchemy / Pydantic)
* **Data Model**: Python's `datetime.date` class must represent start and end dates.
* **SQLAlchemy Mapping**: Map dates directly to SQLAlchemy's `Date` type.
* **Pydantic Schemas**: Fields must be defined as `datetime.date` type. Pydantic v2 automatically parses incoming ISO-8601 strings (e.g. `"2026-06-20"`) into timezone-naive `datetime.date` objects.
* **Computations**: All interval calculations (e.g. cycle length, predictions) must use pure `datetime.date` objects and `datetime.timedelta`. Avoid `datetime.datetime` and any timezone aware datetimes (`tzinfo`) for these calculations.

### 2.3 Frontend (React / Vite / TypeScript)
* **Date Representation**: Keep dates as timezone-naive `YYYY-MM-DD` strings.
* **Input Handling**: The standard HTML `<input type="date">` browser component operates entirely on `YYYY-MM-DD` local strings. Read and write these values directly as strings. Do not convert them to UTC `Date` objects.
* **Safe Parsing (Avoiding Browser UTC Shifts)**:
  - **Incorrect**: `new Date(dateStr)` parses YYYY-MM-DD as UTC midnight. In timezones behind UTC (like UTC-5), this shifts the date to the previous calendar day (e.g., `2026-06-20` becomes `June 19th` in local time).
  - **Correct**: Append `T00:00:00` before parsing, i.e., `new Date(dateStr + 'T00:00:00')`. This forces the browser to instantiate the date object in the user's local timezone at midnight, matching the exact calendar day.
* **Safe Local Date String Generation**:
  - To generate "today" in local YYYY-MM-DD format:
    ```typescript
    const today = new Date()
    const year = today.getFullYear()
    const month = String(today.getMonth() + 1).padStart(2, '0')
    const day = String(today.getDate()).padStart(2, '0')
    const localDateStr = `${year}-${month}-${day}`
    ```
* **Date Comparisons**: Since `YYYY-MM-DD` is a lexicographically sortable string format, perform simple comparison and sorting without instantiating `Date` objects:
  - **Comparison**: `endDate < startDate`
  - **Sorting**: `dates.sort((a, b) => b.localeCompare(a))`

---

## 3. Implementation Rules

1. **API Requests & Responses**: The API must accept and return dates as `YYYY-MM-DD` strings (e.g., `"2026-06-20"`). It must not contain timezone indicators (`Z`, `+00:00`).
2. **Backend Calculations**: The backend must compute prediction gaps using timezone-naive delta operations: `(date2 - date1).days`.
3. **No Timezone Assumptions**: No code in either the frontend or backend should check the system's timezone or assume UTC offsets when dealing with cycle dates.
