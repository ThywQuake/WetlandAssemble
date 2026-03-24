# SWAMPS Loader Variable Name Fix

**Issue:** SWAMPS loader expects `fw` variable but HPC files may have different variable names.

**Error:**
```
KeyError: 'fw'
at swamps.py:54: dataset = source[list(data_vars)].rename(data_vars)
```

**Root Cause:**
Line 51 hardcodes `data_vars = {"fw": "wetland_fraction"}` but actual SWAMPS NetCDF files may use different variable names (e.g., `surface_water_fraction`, `Fw`, `inundation`).

**Fix:**
Make SWAMPS loader robust to variable name variations by checking what's actually in the file.

## Implementation

```python
# src/WA/loaders/swamps.py, line 50-54

source = xr.open_dataset(path)

# Detect wetland fraction variable (try common names)
fw_candidates = ["fw", "Fw", "surface_water_fraction", "inundation"]
fw_var = next((v for v in fw_candidates if v in source), None)
if fw_var is None:
    raise ValueError(f"No wetland fraction variable found in {path}. Available: {list(source.data_vars)}")

data_vars = {fw_var: "wetland_fraction"}
if "flag" in source:
    data_vars["flag"] = "flag"
dataset = source[list(data_vars)].rename(data_vars)
```

**Alternative:** Check one sample file on HPC first to confirm actual variable name, then update loader accordingly.

**HPC Command to Diagnose:**
```bash
uv run python -c "import xarray as xr; ds = xr.open_dataset('/lustre/home/2200013429/Wetland_Assemble/data/SWAMPS/stable/1992/01/*.nc'); print(list(ds.data_vars))"
```
