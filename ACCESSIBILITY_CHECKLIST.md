# Accessibility Checklist

Complete accessibility audit checklist based on WCAG 2.1 AA standards.

---

## Perceivable

### Text Alternatives
- [ ] All images have alt text
- [ ] Decorative images have empty alt (`alt=""`)
- [ ] Complex images have detailed descriptions
- [ ] Icons have appropriate labels
- [ ] Charts/graphs have text alternatives

### Time-based Media
- [ ] Videos have captions (if applicable)
- [ ] Audio has transcripts (if applicable)
- [ ] Auto-playing media can be paused

### Adaptable
- [ ] Content can be presented without losing information
- [ ] Information not conveyed by color alone
- [ ] Text can be resized up to 200% without loss of functionality
- [ ] Content reflows properly on zoom

### Distinguishable
- [ ] Color contrast meets WCAG AA standards (4.5:1 for text)
- [ ] Large text contrast meets standards (3:1)
- [ ] Text is readable and clear
- [ ] Background and foreground colors distinguishable
- [ ] Audio controls available (if applicable)

---

## Operable

### Keyboard Accessible
- [ ] All functionality available via keyboard
- [ ] No keyboard traps
- [ ] Tab order is logical
- [ ] Focus indicators visible
- [ ] Skip links available
- [ ] Keyboard shortcuts documented (if applicable)

### Enough Time
- [ ] No time limits (or adjustable)
- [ ] Auto-updating content can be paused/stopped
- [ ] No moving/blinking content that can't be paused

### Seizures and Physical Reactions
- [ ] No content flashes more than 3 times per second
- [ ] No animations that could cause seizures

### Navigable
- [ ] Page titles are descriptive
- [ ] Headings are properly structured (h1, h2, h3, etc.)
- [ ] Focus order is logical
- [ ] Multiple ways to find content
- [ ] Link purpose is clear from context
- [ ] Headings and labels are descriptive

### Input Modalities
- [ ] Touch targets are at least 44x44 pixels
- [ ] Gestures can be cancelled
- [ ] Functionality available without complex gestures

---

## Understandable

### Readable
- [ ] Language of page is specified (`lang` attribute)
- [ ] Language changes are marked
- [ ] Unusual words are explained
- [ ] Abbreviations are explained
- [ ] Reading level is appropriate

### Predictable
- [ ] Navigation is consistent
- [ ] Components with same functionality are identified consistently
- [ ] Changes of context are initiated by user
- [ ] No unexpected changes on focus/input

### Input Assistance
- [ ] Error messages are clear and specific
- [ ] Error suggestions are provided
- [ ] Labels and instructions are provided
- [ ] Required fields are indicated
- [ ] Error prevention (confirmations for important actions)

---

## Robust

### Compatible
- [ ] Valid HTML
- [ ] Proper use of ARIA attributes
- [ ] Name, role, value are programmatically determinable
- [ ] Status messages are announced
- [ ] Dynamic content updates are announced

---

## ARIA Implementation

### Landmarks
- [ ] `<header>` or `role="banner"`
- [ ] `<nav>` or `role="navigation"`
- [ ] `<main>` or `role="main"`
- [ ] `<footer>` or `role="contentinfo"`

### Labels
- [ ] All form inputs have labels
- [ ] Buttons have accessible names
- [ ] Links have descriptive text
- [ ] Icons have aria-labels

### States and Properties
- [ ] Form validation states announced
- [ ] Loading states announced
- [ ] Error states announced
- [ ] Disabled states communicated

### Live Regions
- [ ] Dynamic content updates announced
- [ ] Status messages use appropriate live regions
- [ ] Alerts use `role="alert"`

---

## Testing Methods

### Automated Testing
- [ ] Run Lighthouse accessibility audit
- [ ] Use axe DevTools
- [ ] Run WAVE browser extension
- [ ] Check with automated tools

### Manual Testing
- [ ] Test with keyboard only
- [ ] Test with screen reader (NVDA/JAWS/VoiceOver)
- [ ] Test with browser zoom (200%)
- [ ] Test with high contrast mode
- [ ] Test color contrast with tools

### User Testing
- [ ] Test with users who use assistive technologies
- [ ] Gather feedback from disabled users
- [ ] Test with various devices

---

## Common Issues to Check

### Images
- [ ] All images have alt text
- [ ] Decorative images have empty alt
- [ ] Complex images have descriptions

### Forms
- [ ] All inputs have labels
- [ ] Error messages are clear
- [ ] Required fields indicated
- [ ] Validation feedback accessible

### Links
- [ ] Link text is descriptive
- [ ] Links are distinguishable
- [ ] No "click here" links
- [ ] External links indicated

### Headings
- [ ] Proper heading hierarchy (h1 → h2 → h3)
- [ ] No skipped heading levels
- [ ] Headings are descriptive

### Color
- [ ] Information not conveyed by color alone
- [ ] Color contrast meets standards
- [ ] Focus indicators visible

### Keyboard
- [ ] All functionality keyboard accessible
- [ ] Tab order logical
- [ ] Focus indicators visible
- [ ] No keyboard traps

---

## Tools

### Browser Extensions
- **axe DevTools** - Automated accessibility testing
- **WAVE** - Web accessibility evaluation
- **Lighthouse** - Built into Chrome DevTools

### Screen Readers
- **NVDA** (Windows, free)
- **JAWS** (Windows, paid)
- **VoiceOver** (macOS/iOS, built-in)
- **TalkBack** (Android, built-in)

### Color Contrast
- **WebAIM Contrast Checker**
- **Colour Contrast Analyser**
- **Chrome DevTools** - Color picker with contrast ratio

---

## Quick Test Checklist

### 5-Minute Test
1. [ ] Tab through entire page
2. [ ] Check all images have alt text
3. [ ] Verify color contrast
4. [ ] Test with screen reader (basic)
5. [ ] Run Lighthouse accessibility audit

### 15-Minute Test
1. [ ] Complete 5-minute test
2. [ ] Test all forms
3. [ ] Test all interactive elements
4. [ ] Check heading structure
5. [ ] Verify ARIA labels
6. [ ] Test with browser zoom

### Full Audit
1. [ ] Complete 15-minute test
2. [ ] Test with multiple screen readers
3. [ ] Test with keyboard only
4. [ ] Test with high contrast
5. [ ] Review all WCAG criteria
6. [ ] Document findings

---

## Accessibility Helper Functions

### Using Built-in Helper
```javascript
// Run accessibility audit
accessibilityHelper.runAudit();

// Check keyboard accessibility
accessibilityHelper.isKeyboardAccessible(element);

// Announce to screen reader
accessibilityHelper.announce(message);
```

### Using Test Helpers
```javascript
// Run accessibility tests
testHelpers.runAccessibilityAudit();
testHelpers.testKeyboardNavigation();
testHelpers.validateHTMLStructure();
```

---

## Resources

- **WCAG 2.1 Guidelines:** https://www.w3.org/WAI/WCAG21/quickref/
- **WebAIM:** https://webaim.org/
- **A11y Project:** https://www.a11yproject.com/
- **MDN Accessibility:** https://developer.mozilla.org/en-US/docs/Web/Accessibility

---

**Last Updated:** 2025-01-21

