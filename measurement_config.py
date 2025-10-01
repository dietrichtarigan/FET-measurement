# FET Measurement GUI Configuration
# This file contains default settings that can be modified by users

DEFAULT_SETTINGS = {
    # Instrument GPIB Addresses
    'GPIB_VDS': 'GPIB0::24::INSTR',
    'GPIB_VG': 'GPIB0::18::INSTR',
    
    # Current Limits (A)
    'VDS_CURRENT_LIMIT': 0.1,
    'VG_CURRENT_LIMIT': 0.1,
    
    # Default measurement parameters for ID-VD
    'IDVD_DEFAULTS': {
        'VG_FROM': 0,
        'VG_TO': 10,
        'VG_STEP': 5,
        'VG_DELAY': 0.5,
        'VDS_FROM': -1,
        'VDS_TO': 1,
        'VDS_STEP': 0.05,
        'VDS_DELAY': 0.2
    },
    
    # Default measurement parameters for ID-VG
    'IDVG_DEFAULTS': {
        'VDS_FROM': 0.2,
        'VDS_TO': 0.4,
        'VDS_STEP': 0.2,
        'VDS_DELAY': 0.5,
        'VG_FROM': -10,
        'VG_TO': 10,
        'VG_STEP': 0.5,
        'VG_DELAY': 0.2
    },
    
    # Plot settings
    'PLOT_SETTINGS': {
        'FIGURE_SIZE': (8, 6),
        'DPI': 100,
        'GRID': True,
        'MARKER_SIZE': 2,
        'LINE_WIDTH': 1
    },
    
    # File settings
    'FILE_SETTINGS': {
        'AUTO_TIMESTAMP': True,
        'CSV_DELIMITER': ',',
        'BACKUP_ENABLED': True
    }
}