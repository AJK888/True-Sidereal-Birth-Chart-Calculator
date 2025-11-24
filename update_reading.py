import json

# Read the current file
with open('True-Sidereal-Birth-Chart-Calculator/examples/data/elon-musk.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Read the complete reading from a text file
try:
    with open('elon_complete_reading.txt', 'r', encoding='utf-8') as f:
        reading = f.read()
except FileNotFoundError:
    # Fallback: use the overview section if file doesn't exist
    reading = """Chart Overview and Core Themes

Welcome. Your astrological chart is a remarkable document, a blueprint that maps the intricate relationship between your soul's enduring purpose and the personality you've developed to navigate this lifetime. The analysis reveals a life path of profound depth, centered on the challenge of bringing a rich, private inner world into the light through a disciplined and heart-centered creative process. There is a consistent and powerful tension in your chart between a soul designed for communication and a personality wired for privacy and protection. Your life is the story of building a bridge between these two worlds, and your tools for this construction are creative expression and a deep-seated sense of responsibility. As we explore this map, we will see that your greatest challenges are also the source of your most unique and powerful gifts. Three core themes emerge as the central pillars of your life's architecture.

The first and most foundational theme is what can be called **The Voice from the Subconscious**. At your core, you are a "hidden messenger." Your Sidereal blueprint, reflecting your soul's purpose, shows a Sun and Ascendant in the communicative, intellectual sign of Gemini. Your soul is here to connect, to articulate, and to disseminate information. However, this entire purpose is filtered through the 12th House, the realm of the subconscious, spirit, and all that is hidden from plain view. This creates a fascinating paradox: a soul designed to be a broadcaster, but whose studio is located in a secret, internal sanctuary. This soul-level design manifests through a personality, described by your Tropical chart, that is inherently private and protective, with a Sun and Ascendant in the sensitive sign of Cancer. Your personality instinct is to retreat, to nurture, and to create a safe emotional shell. This reinforces the 12th House placement, making your conscious self naturally shy and your vitality replenished in solitude. The central life task is to reconcile the soul's need to speak with the personality's need for safety. Your purpose is not to be a public orator, but to become a trusted voice for the subtle, emotional, and spiritual currents that flow beneath the surface of everyday life.

Your primary tool for building this bridge is found in the second core theme: **Self-Worth Defined by Creative Expression and Recognition**. This is the most powerful and integrated aspect of your entire chart. Both your soul's deep-seated need and your personality's emotional expression are perfectly aligned in the sign of Leo, located in the 2nd House of self-worth and personal values. Your emotional well-being, your sense of security, and your very definition of value are fundamentally and inextricably linked to your ability to express yourself with creativity, warmth, and authentic pride. The Moon, your dominant planet, insists that this is not a hobby but a vital necessity. You feel secure when you are creating and when that creation is seen, valued, and celebrated. This theme is further amplified by your Day Number of 1, underscoring a core drive to be seen as a unique individual and a leader in your creative domain. This powerful Leonine engine is the fuel that gives you the courage to overcome the inherent shyness of your Cancerian personality, pushing your inner world out into the open so it can be recognized and affirmed. Your art, in whatever form it takes, is not just something you do; it is the tangible proof of your value in the world.

These two dynamics—the hidden messenger and the creative powerhouse—are ultimately in service of your third foundational theme: **The Nurturer's Responsibility**. This theme acts as the ultimate container and purpose for your life's work. Your Life Path Number is 6, the number of the caregiver, healer, and community steward. This is reinforced by your Chinese Zodiac sign of the Earth Goat, noted for its gentle, artistic, and nurturing disposition. Astrologically, this is powerfully reflected in the Cancerian placements that define your personality (Tropical Sun/Ascendant) and inform your soul's thinking and expansion (Sidereal Mercury/Jupiter). Your life is fundamentally oriented toward creating emotional security, not just for yourself, but for others. This is the "why" behind your actions. You are driven to use your voice (Theme 1) and your creative gifts (Theme 2) to heal, protect, and provide for your chosen "family" or community. The journey of your Nodal Axis confirms this entire story: your soul is evolving away from a past of depending on others' resources and navigating shared crises (South Node in the 8th House) toward a future of building your own solid foundation of value through tangible, creative craftsmanship (North Node in the 2nd House). Your life's mission is to become the sovereign creator of your own security so that you may, in turn, become a stable, nurturing, and inspiring presence for others.

Your path is therefore one of profound integration. It is the journey of the sensitive soul who must learn to become a courageous artist, the private individual who must find a public voice, and the creative sovereign who must learn that their greatest power lies in their capacity to care for their kingdom. By embracing your creative fire, you build the confidence to speak your hidden truths, and in speaking those truths, you fulfill your ultimate purpose as a healer and a source of security in the world. This is the alchemical work of turning private feeling into a tangible, heart-centered, and beautifully crafted contribution to the world."""
    print("Note: Using fallback reading. To use the complete reading, create 'elon_complete_reading.txt' with the full text.")

# Update the reading field
data['ai_reading'] = reading

# Write back to file
with open('True-Sidereal-Birth-Chart-Calculator/examples/data/elon-musk.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("✓ Updated elon-musk.json with the complete reading")

