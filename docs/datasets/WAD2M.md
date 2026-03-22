---
Year Range: 2000-2018
Resolution (m): 0.25 deg * 0.25 deg
Product Type: Active and Passive Microwave Remote Sensing
Article Link: https://essd.copernicus.org/articles/13/2001/2021/
Dynamic: true
---
## Abstract

Seasonal and interannual variations in global wetland area are a strong driver of fluctuations in global methane (CH4) emissions. Current maps of global wetland extent vary in their wetland definition, causing substantial disagreement between and large uncertainty in estimates of wetland methane emissions. To reconcile these differences for large-scale wetland CH4 modeling, we developed the global Wetland Area and Dynamics for Methane Modeling (WAD2M) version 1.0 dataset at a ∼ ==25 km== resolution at the Equator (0.25∘) at a monthly time step for ==2000–2018==. WAD2M combines a time series of surface inundation based on active and passive microwave remote sensing at a coarse resolution with six static datasets that discriminate inland waters, agriculture, shoreline, and non-inundated wetlands. We excluded all permanent water bodies (e.g., lakes, ponds, rivers, and reservoirs), coastal wetlands (e.g., mangroves and sea grasses), and rice paddies to only represent spatiotemporal patterns of inundated and non-inundated vegetated wetlands. Globally, WAD2M estimates the long-term maximum wetland area at 13.0×106 km2 (13.0 Mkm2), which can be divided into three categories: mean annual minimum of inundated and non-inundated wetlands at 3.5 Mkm2, seasonally inundated wetlands at 4.0 Mkm2 (mean annual maximum minus mean annual minimum), and intermittently inundated wetlands at 5.5 Mkm2(long-term maximum minus mean annual maximum).

## Data Profile

<bound method Dataset.info of <xarray.Dataset> Size: 2GB
Dimensions:    (time: 252, bnds: 2, lat: 720, lon: 1440)
Coordinates:
  * time       (time) datetime64[ns] 2kB 2000-01-16 2000-02-15 ... 2020-12-16
  * lat        (lat) float64 6kB 89.88 89.62 89.38 ... -89.38 -89.62 -89.88
  * lon        (lon) float64 12kB -179.9 -179.6 -179.4 ... 179.4 179.6 179.9
Dimensions without coordinates: bnds
Data variables:
    time_bnds  (time, bnds) datetime64[ns] 4kB ...
    Fw         (time, lat, lon) float64 2GB ...
Attributes:
    history:  Project: Global Carbon Project CH4 v2\nCreated by: benjamin.pou...>