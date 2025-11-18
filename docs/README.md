# Media Scheduler

## Overview

Media Scheduler is an intelligent vehicle-to-media-partner assignment optimization system designed for DriveShop. It efficiently schedules which media partners receive which vehicles for media coverage during specific time periods.

## What It Does

This system manages the complex logistics of matching vehicles with media partners by:

- **Optimizing assignments** using constraint satisfaction algorithms to match 400+ vehicles across 7 offices with 200+ media partners
- **Balancing objectives** including publication rates, vehicle quality, partner preferences, and geographic proximity
- **Enforcing constraints** like cooldown periods, budget limits, partner availability, and vehicle capabilities
- **Generating chains** of 4-6 sequential, non-overlapping vehicle loans per partner
- **Integrating with FMS** (Fleet Management System) for bi-directional workflow management

## Key Features

### Optimizer Engine
Run global constraint satisfaction optimization using Google OR-Tools to automatically assign vehicles to partners based on configurable policy weights for local priority, publishing success, tier distribution, and budget awareness.

### Chain Builder
Build assignment chains in two modes:
- **Partner Chain Mode**: Select a partner and get 4-6 optimal sequential vehicles
- **Vehicle Chain Mode**: Select a vehicle and get 4-6 optimal sequential partners

### Calendar View
Visualize and manage assignments over time with drag-and-drop functionality, color-coded status indicators, and detailed context windows for vehicles and partners.

### FMS Integration
Seamless bi-directional integration with DriveShop's Fleet Management System for creating, updating, and tracking vehicle requests.

### Data Management
Comprehensive data ingestion from CSV, Excel, and FMS report URLs with automatic nightly synchronization.

## Who Is This For?

- **Fleet Coordinators**: Schedule and manage vehicle assignments
- **Operations Managers**: Monitor capacity and optimize resource allocation
- **Media Relations Teams**: Track partner assignments and publication success

## Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19, Vite, Tailwind CSS, Headless UI |
| Backend | FastAPI (Python 3.12), uvicorn |
| Database | Supabase (PostgreSQL) |
| Optimization | Google OR-Tools CP-SAT Solver |
| Deployment | Render, Docker |

## Quick Start

1. Navigate to the Media Scheduler application
2. Select your office from the dropdown
3. Choose your workflow:
   - **Optimizer**: Run automated assignment optimization
   - **Chain Builder**: Build individual assignment chains
   - **Calendar**: View and manage existing assignments

See the [Getting Started](getting-started.md) guide for detailed instructions.

## Support

For technical support or feature requests, contact the development team or submit an issue through the project repository.
