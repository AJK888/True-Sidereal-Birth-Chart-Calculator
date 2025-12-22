# Developer Guide: Synthesis Astrology Frontend

## Overview

This guide documents the frontend architecture, module structure, and development practices for the Synthesis Astrology website.

## Architecture

### Module Structure

The frontend uses a modular architecture with the following core modules:

```
assets/js/
├── api-client.js          # Unified API communication layer
├── state-manager.js       # Centralized state management
├── form-validator.js      # Form validation with real-time feedback
├── performance-monitor.js # Performance tracking and Core Web Vitals
├── error-tracker.js       # Error tracking and reporting
├── calculator.js          # Main chart calculation logic
├── auth.js                # Authentication and user management
└── click-tracker.js       # User interaction tracking
```

### Core Modules

#### API Client (`api-client.js`)

Centralized API communication layer that handles all backend requests.

**Usage:**
```javascript
// Calculate a chart
const chartData = await apiClient.calculateChart({
  full_name: "John Doe",
  year: 1990,
  month: 1,
  day: 1,
  hour: 12,
  minute: 0,
  location: "New York, NY, USA",
  unknown_time: false,
  user_email: "user@example.com"
});

// Generate a reading
const reading = await apiClient.generateReading(chartData, userInputs);

// Find similar famous people
const matches = await apiClient.findSimilarFamousPeople(chartData, 10);
```

**Features:**
- Automatic friends & family key handling
- Consistent error handling
- Request/response logging
- Fallback support

#### State Manager (`state-manager.js`)

Event-driven state management for application-wide state.

**Usage:**
```javascript
// Subscribe to state changes
const unsubscribe = stateManager.subscribe('currentChartData', (newData, oldData, fullState) => {
  console.log('Chart data updated:', newData);
  updateUI(newData);
});

// Update state
stateManager.setState('currentChartData', chartData);
stateManager.setState('isLoading', true);

// Get state
const chartData = stateManager.getState('currentChartData');
const allState = stateManager.getState();

// Unsubscribe
unsubscribe();
```

**State Keys:**
- `currentChartData` - Currently calculated chart data
- `currentUserInputs` - User input data
- `isLoading` - Loading state flag
- `user` - Current authenticated user
- `savedCharts` - User's saved charts

#### Form Validator (`form-validator.js`)

Real-time form validation with visual feedback.

**Usage:**
```javascript
// Initialize validator
const validator = new FormValidator(document.getElementById('chartForm'));

// Validation happens automatically on:
// - Field blur events
// - Form submit

// Check validation status
if (validator.hasErrors()) {
  const errors = validator.getErrors();
  console.log('Validation errors:', errors);
}
```

**Supported Validations:**
- Required fields
- Email format
- Birth date format (MM/DD/YYYY)
- Birth time format (HH:MM AM/PM)
- Location minimum length

#### Performance Monitor (`performance-monitor.js`)

Tracks Core Web Vitals and custom performance metrics.

**Usage:**
```javascript
// Monitor is auto-initialized, but you can track custom metrics:

// Track a custom metric
performanceMonitor.trackMetric('chart_calculation_time', 1234);

// Use timer for automatic tracking
const stopTimer = performanceMonitor.startTimer('api_call');
await apiCall();
stopTimer(); // Automatically records elapsed time

// Get all metrics
const metrics = performanceMonitor.getMetrics();
```

**Tracked Metrics:**
- LCP (Largest Contentful Paint)
- FID (First Input Delay)
- CLS (Cumulative Layout Shift)
- Page load timing
- Navigation timing
- Custom metrics

#### Error Tracker (`error-tracker.js`)

Centralized error tracking and reporting.

**Usage:**
```javascript
// Errors are automatically tracked, but you can track custom errors:

// Track custom error
errorTracker.trackError('Custom error message', {
  context: 'chart_calculation',
  userId: '123'
});

// Track API errors
try {
  await apiCall();
} catch (error) {
  errorTracker.trackAPIError('/api/endpoint', error, requestData);
}
```

**Tracked Errors:**
- JavaScript errors
- Unhandled promise rejections
- API errors
- Custom errors

## Development Practices

### Code Style

- Use JSDoc comments for all public methods
- Follow existing code patterns
- Use meaningful variable names
- Keep functions focused and small

### Error Handling

Always use the error tracker for errors:

```javascript
try {
  const result = await apiClient.calculateChart(data);
} catch (error) {
  errorTracker.trackAPIError('/calculate_chart', error, data);
  // Show user-friendly error message
  showError(errorTracker.formatErrorMessage(error));
}
```

### State Management

Use the state manager for application-wide state:

```javascript
// Update state
stateManager.setState('isLoading', true);

// Subscribe to changes
stateManager.subscribe('isLoading', (isLoading) => {
  updateLoadingUI(isLoading);
});
```

### Performance

Track performance for important operations:

```javascript
const stopTimer = performanceMonitor.startTimer('chart_calculation');
// ... do work ...
stopTimer();
```

### Form Validation

Always use the form validator for forms:

```javascript
const validator = new FormValidator(form);
// Validation happens automatically
```

## Build Process

### Vite Configuration

The project uses Vite for building:

- **Build Command:** `npm run build`
- **Output Directory:** `dist/`
- **Public Directory:** `public/` (copied as-is)

### Asset Management

- Source files: `assets/`
- Static assets: `public/`
- Build output: `dist/`

Files in `public/assets/js/` are copied to `dist/assets/js/` during build.

## Testing

### Manual Testing Checklist

- [ ] Form validation works on all fields
- [ ] API calls succeed and handle errors
- [ ] State updates trigger UI updates
- [ ] Performance metrics are tracked
- [ ] Errors are logged correctly
- [ ] Mobile experience is functional
- [ ] Accessibility features work (keyboard nav, screen readers)

### Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## Performance Targets

- **Lighthouse Score:** > 90
- **LCP:** < 2.5s
- **FID:** < 100ms
- **CLS:** < 0.1
- **Time to Interactive:** < 3.5s

## Accessibility

- WCAG 2.1 AA compliance
- Keyboard navigation support
- Screen reader support
- ARIA labels on interactive elements
- Focus indicators

## Troubleshooting

### Common Issues

**API calls failing:**
- Check if `apiClient` is available
- Verify API endpoint URLs
- Check network tab for errors

**State not updating:**
- Verify subscription is active
- Check if state key is correct
- Ensure `setState` is being called

**Form validation not working:**
- Verify form element is passed to validator
- Check if validator is initialized
- Ensure form has proper input types

## Contributing

1. Follow existing code patterns
2. Add JSDoc comments for new functions
3. Test in multiple browsers
4. Check accessibility
5. Monitor performance impact

## Resources

- [API Documentation](../api.py)
- [UX Rebuild Plan](../UX_REBUILD_PLAN.md)
- [Vite Setup Guide](./VITE_SETUP.md)

