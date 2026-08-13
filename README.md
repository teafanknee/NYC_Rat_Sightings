# NYC Rat Sighting Analysis

Geospatial analysis and interactive dashboard identifying clusters of rat
activity across New York City, built on 311 service request data.

## Overview

New York City's 311 hotline handles non-emergency service requests from
residents. Rodent complaints are more than a nuisance - it's a public
health issue. Rats transmit diseases and contaminate food, and their
distribution is closely tied to waste management.

This project uses reported rat sightings as a proxy for rat activity to
identify where infestations concentrate geographically, and to surface
neighborhood-level patterns that could inform how sanitation and public
health resources should be implemented.

## Data

**Source:** [311 Service Requests from 2020 to Present]([https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2020-to-Present/erm2-nwe9/about_data]) — NYC Open Data

The dataset is updated daily. This analysis uses a snapshot retrieved on
**June 2, 2025**, filtered to rodent-related complaints.

Note that the data reflects *reported* sightings rather than true rat
density, and is therefore subject to reporting bias. Areas with higher
civic engagement may appear more affected than areas with equal or worse
infestation but lower reporting rates.

## Methods

K-Means clustering on sighting coordinates to identify activity hotspots,
with results aggregated to neighborhood level and assigned risk tiers.

## Dashboard

Interactive Streamlit application with a map of clustered sightings and
neighborhood risk tiers, allowing filtering by [time period / borough /
cluster].
