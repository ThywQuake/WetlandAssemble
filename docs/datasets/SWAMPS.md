---
Year Range: 1992-2018
Resolution (m): 25km
Product Type: Active and Passive Microwave Remote Sensing
Article Link: https://ieeexplore.ieee.org/document/8662682
Dynamic: true
Classification: false
---
### Abstract

This letter summarizes substantial modifications made to the Surface Water Microwave Product Series (SWAMPS), a coarse-resolution (~25 km) global inundated ==area fraction data== record derived from active and passive microwave remote sensing...

### C. Defining Arid and Semiarid Land Covers

The SWAMPS algorithm estimates erroneously high water fraction over some arid and semiarid regions, including sandy deserts, arid zones, salt pans, and ephemeral water bodies. SWAMPS relies on a static land cover map derived from MODIS [21] and assumes consistent emissivity and backscatter properties over each general International Geosphere-Biosphere Programme (IGBP) land cover class. The anomalous fw retrievals observed over arid and semiarid regions are associated with the large surface emissivity and backscatter gradients found within the general “Barren or Sparsely Vegetated” (BSV) land cover class across the globe. The variability of microwave measurements observed in this class arise from two primary complicating factors: 1) the emissivity of bare ground is highly influenced by the soil’s dominant mineral composition [22] and 2) multitemporal variation in semiarid regions with pronounced seasonal changes in vegetation cover, e.g., Africa’s Sahel.

In SWAMPSv3, the general BSV class was partitioned into subsets of bare surface types with similar emissivity and backscatter character. A k -means clustering analysis of the 33 unique surface types identified by the Harmonized World Soil Database (HWSD) [23] was performed based on a climatology of monthly means of gridded 19-GHz MPDI and C-band σ0 for representative 25 km ×25 km grid cells (>95% BSV, where >85% is represented by a single soil type). Six clusters were selected to segment the general BSV class.

Time series of NDVI was used as a dynamic measure of vegetation cover to delineate arid (permanently nonvegetated) and semiarid (seasonally vegetated) areas. Three statistics were calculated and averaged for both the AVHRR-based record (1992–2000) and MODIS-based record (2000–2018) globally at the original product spatial resolution: 1) annual maximum (NDVIymax ); 2) annual minimum (NDVIymin ); and 3) annual standard deviation (NDVIystd ). Arid and semiarid regions were identified using a definition first developed by Gamo _et al._ [24], and areas labeled as urban, water, or ice by the native 1-km MODIS land cover product (MODIS-IGBP) were excluded. Arid regions were defined as pixels with NDVIymax less than 0.15 and NDVIystd less than 0.03. Semiarid regions were defined as regions with NDVIymin less than 0.15 and NDVIystd less than 0.4. The same thresholds were used for both AVHRR- and MODIS-based records.

The fractional land cover map employed by the SWAMPS algorithm was recalculated at each time period (t ) an NDVI composite was available (bimonthly for AVHRR and 16 days for MODIS) using subgrid cell, static land cover from MODIS-IGBP, and dynamic vegetation conditions from NDVI_t_. The general BSV class was eliminated and replaced with six different bare ground classes (“Bare Ground 1–6”) and a vegetation class named “Sparse Vegetation.” All pixels labeled as BSV by MODIS-IGBP were reclassified to the appropriate bare ground class corresponding to its HWSD soil type. For all pixels identified as semiarid, an additional decision was executed: 1) semiarid BSV pixels with NDVI_t_ greater than 0.15 were reassigned as “Sparse Vegetation” and 2) semiarid pixels not classified by MODIS-IGBP as BSV but with NDVI_t_ less than 0.15 were reassigned to their appropriate bare ground class.

The land cover-specific regression models used for approximating seasonal biomass dynamics at each segment (Table I) were redeveloped for each land cover class based on these modified, dynamic land cover maps.

### D. Flags

Prior versions of SWAMPS screened for snow cover using a classification and conservative 28-day running average of estimated snow water equivalent (SWE) based on daily Tb observations. This generally overestimated snow cover extent and tends to be overly restrictive, eliminating potentially useful observations after snowpack melt. In this update, we opted to rely on ancillary snow cover products in screening for snow cover. Segment I (Table I) relies on the monthly SWE estimates based on SSM/I [17], similar to what was used in the original version of SWAMPS due to the scarcity of data. However, segments II and III depend on the higher resolution, eight-day MODIS fractional snow cover product [18]. If more than 50% of the MODIS pixels within a 25 km ×25 km grid cell observe a snow fraction greater than 25%, then that grid cell is flagged as snow. Any gaps in the snow cover product are filled with a climatological value derived over the MODIS record, 2000–2017.

Any 25 km ×25 km grid cell that is observed to be greater than 99% arid as defined in Section II-C is flagged as arid. The rationale is that inundation is highly unlikely in these regions and the signal-to-noise ratio is low.

### E. Water Fraction Definition

Prior versions of SWAMPS reported the estimated dynamics of nonpermanent surface water area, excluding water bodies and permanently inundated areas. In an effort to facilitate the use of this data set with complementary products, SWAMPSv3 includes all terrestrial water fractions within the fw retrieval. An ancillary data layer now includes the fractions of permanent water and permanently inundated areas so that they can be accounted for separately, if needed.

## Data Profile

<bound method Dataset.info of <xarray.Dataset> Size: 4MB
 Dimensions:  (lat: 586, lon: 1383)
 Coordinates:
   * lat      (lat) float32 2kB 85.31 83.34 81.83 80.55 ... -81.83 -83.34 -85.31
   * lon      (lon) float32 6kB -179.9 -179.6 -179.3 -179.1 ... 179.3 179.6 179.9
 Data variables:
     fw       (lat, lon) float32 3MB ...
     flag     (lat, lon) int8 810kB ...
 Attributes:
     description:      Global SWAMPS inundation fraction projected in 25km EAS...
     product_version:  3.2>,