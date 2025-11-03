/**
 * Global Event Manager for cross-component communication
 *
 * Enables Chain Builder and Calendar to communicate without prop drilling
 * or complex state management libraries.
 *
 * Events:
 * - 'chainDataUpdated': Chain Builder saved/deleted data → Calendar should reload
 * - 'calendarDataUpdated': Calendar saved/deleted data → Chain Builder should reload
 */

export const EventManager = {
  /**
   * Emit a custom event with optional detail payload
   * @param {string} eventName - The event name
   * @param {object} detail - Optional data to pass with the event
   */
  emit: (eventName, detail = {}) => {
    window.dispatchEvent(new CustomEvent(eventName, { detail }));
    // Safe logging - avoid circular references
    try {
      console.log(`[EventManager] Emitted: ${eventName}`, JSON.parse(JSON.stringify(detail)));
    } catch (err) {
      console.log(`[EventManager] Emitted: ${eventName}`, '[Complex object - cannot stringify]');
    }
  },

  /**
   * Listen for a custom event
   * @param {string} eventName - The event name to listen for
   * @param {function} callback - Callback function that receives event detail
   */
  on: (eventName, callback) => {
    const handler = (e) => {
      // Safe logging - avoid circular references
      try {
        console.log(`[EventManager] Received: ${eventName}`, JSON.parse(JSON.stringify(e.detail)));
      } catch (err) {
        console.log(`[EventManager] Received: ${eventName}`, '[Complex object - cannot stringify]');
      }
      callback(e.detail);
    };
    window.addEventListener(eventName, handler);
    return handler; // Return for cleanup
  },

  /**
   * Remove event listener
   * @param {string} eventName - The event name
   * @param {function} handler - The handler function to remove
   */
  off: (eventName, handler) => {
    window.removeEventListener(eventName, handler);
    console.log(`[EventManager] Removed listener: ${eventName}`);
  }
};

/**
 * Event Types - For type safety and documentation
 */
export const EventTypes = {
  CHAIN_DATA_UPDATED: 'chainDataUpdated',
  CALENDAR_DATA_UPDATED: 'calendarDataUpdated',
  APPLY_VEHICLE_HISTORY_FILTER: 'APPLY_VEHICLE_HISTORY_FILTER', // Filter partner list by vehicle review history
  APPLY_PARTNER_HISTORY_FILTER: 'APPLY_PARTNER_HISTORY_FILTER', // Filter vehicle list by partner review history
  CLEAR_HISTORY_FILTERS: 'CLEAR_HISTORY_FILTERS' // Clear all review history filters
};
