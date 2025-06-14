import swisseph as swe
from datetime import datetime
import pytz
from typing import Dict, List, Tuple, Optional
import math

class AstrologyService:
    def __init__(self):
        # Initialize Swiss Ephemeris
        swe.set_ephe_path('')  # Use default ephemeris path
        
        # Zodiac signs
        self.zodiac_signs = [
            "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
            "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
        ]
        
        # Planet names for Swiss Ephemeris
        self.planets = {
            'Sun': swe.SUN,
            'Moon': swe.MOON,
            'Mercury': swe.MERCURY,
            'Venus': swe.VENUS,
            'Mars': swe.MARS,
            'Jupiter': swe.JUPITER,
            'Saturn': swe.SATURN,
            'Uranus': swe.URANUS,
            'Neptune': swe.NEPTUNE,
            'Pluto': swe.PLUTO
        }
        
        # Country coordinates (approximate major cities)
        self.country_coordinates = {
            'United States': (39.8283, -98.5795),
            'Canada': (56.1304, -106.3468),
            'United Kingdom': (55.3781, -3.4360),
            'Germany': (51.1657, 10.4515),
            'France': (46.2276, 2.2137),
            'Italy': (41.8719, 12.5674),
            'Spain': (40.4637, -3.7492),
            'Russia': (61.5240, 105.3188),
            'China': (35.8617, 104.1954),
            'Japan': (36.2048, 138.2529),
            'India': (20.5937, 78.9629),
            'Australia': (-25.2744, 133.7751),
            'Brazil': (-14.2350, -51.9253),
            'Mexico': (23.6345, -102.5528),
            'Argentina': (-38.4161, -63.6167),
            'South Africa': (-30.5595, 22.9375),
            'Egypt': (26.0975, 30.0444),
            'Turkey': (38.9637, 35.2433),
            'Saudi Arabia': (23.8859, 45.0792),
            'UAE': (23.4241, 53.8478),
            'Israel': (31.0461, 34.8516),
            'Greece': (39.0742, 21.8243),
            'Poland': (51.9194, 19.1451),
            'Netherlands': (52.1326, 5.2913),
            'Belgium': (50.5039, 4.4699),
            'Switzerland': (46.8182, 8.2275),
            'Austria': (47.5162, 14.5501),
            'Sweden': (60.1282, 18.6435),
            'Norway': (60.4720, 8.4689),
            'Denmark': (56.2639, 9.5018),
            'Finland': (61.9241, 25.7482),
            'Portugal': (39.3999, -8.2245),
            'Ireland': (53.4129, -8.2439),
            'Iceland': (64.9631, -19.0208),
            'New Zealand': (-40.9006, 174.8860),
            'South Korea': (35.9078, 127.7669),
            'Thailand': (15.8700, 100.9925),
            'Vietnam': (14.0583, 108.2772),
            'Indonesia': (-0.7893, 113.9213),
            'Malaysia': (4.2105, 101.9758),
            'Singapore': (1.3521, 103.8198),
            'Philippines': (12.8797, 121.7740),
            'Pakistan': (30.3753, 69.3451),
            'Bangladesh': (23.6850, 90.3563),
            'Sri Lanka': (7.8731, 80.7718),
            'Nepal': (28.3949, 84.1240),
            'Iran': (32.4279, 53.6880),
            'Iraq': (33.2232, 43.6793),
            'Afghanistan': (33.9391, 67.7100),
            'Kazakhstan': (48.0196, 66.9237),
            'Uzbekistan': (41.3775, 64.5853),
            'Mongolia': (46.8625, 103.8467),
            'Myanmar': (21.9162, 95.9560),
            'Cambodia': (12.5657, 104.9910),
            'Laos': (19.8563, 102.4955),
            'Nigeria': (9.0820, 8.6753),
            'Kenya': (-0.0236, 37.9062),
            'Ethiopia': (9.1450, 40.4897),
            'Ghana': (7.9465, -1.0232),
            'Morocco': (31.7917, -7.0926),
            'Algeria': (28.0339, 1.6596),
            'Tunisia': (33.8869, 9.5375),
            'Libya': (26.3351, 17.2283),
            'Sudan': (12.8628, 30.2176),
            'Chile': (-35.6751, -71.5430),
            'Peru': (-9.1900, -75.0152),
            'Colombia': (4.5709, -74.2973),
            'Venezuela': (6.4238, -66.5897),
            'Ecuador': (-1.8312, -78.1834),
            'Bolivia': (-16.2902, -63.5887),
            'Paraguay': (-23.4425, -58.4438),
            'Uruguay': (-32.5228, -55.7658),
            'Cuba': (21.5218, -77.7812),
            'Jamaica': (18.1096, -77.2975),
            'Dominican Republic': (18.7357, -70.1627),
            'Haiti': (18.9712, -72.2852),
            'Puerto Rico': (18.2208, -66.5901),
            'Costa Rica': (9.7489, -83.7534),
            'Panama': (8.5380, -80.7821),
            'Guatemala': (15.7835, -90.2308),
            'Honduras': (15.2000, -86.2419),
            'El Salvador': (13.7942, -88.8965),
            'Nicaragua': (12.2650, -85.2072),
            'Belize': (17.1899, -88.4976)
        }
    
    def get_coordinates(self, country: str) -> Tuple[float, float]:
        """Get latitude and longitude for a country."""
        return self.country_coordinates.get(country, (0.0, 0.0))
    
    def calculate_julian_day(self, birth_date: datetime, birth_country: str) -> float:
        """Calculate Julian Day Number for the birth date and location."""
        lat, lon = self.get_coordinates(birth_country)
        
        # Convert to UTC if needed (assuming noon for simplicity)
        utc_date = birth_date.replace(hour=12, minute=0, second=0, microsecond=0)
        
        # Calculate Julian Day
        julian_day = swe.julday(
            utc_date.year,
            utc_date.month,
            utc_date.day,
            utc_date.hour + utc_date.minute/60.0
        )
        
        return julian_day
    
    def get_zodiac_sign(self, longitude: float) -> str:
        """Convert longitude to zodiac sign."""
        sign_index = int(longitude // 30)
        return self.zodiac_signs[sign_index]
    
    def calculate_planetary_positions(self, julian_day: float) -> Dict[str, Dict[str, any]]:
        """Calculate positions of all planets."""
        positions = {}
        
        for planet_name, planet_id in self.planets.items():
            try:
                # Calculate planet position
                result = swe.calc_ut(julian_day, planet_id)
                longitude = result[0][0]  # Longitude in degrees
                
                positions[planet_name] = {
                    'longitude': longitude,
                    'sign': self.get_zodiac_sign(longitude),
                    'degree': longitude % 30,
                    'degree_formatted': f"{int(longitude % 30)}°{int((longitude % 1) * 60)}'"
                }
            except Exception as e:
                print(f"Error calculating {planet_name}: {e}")
                positions[planet_name] = {
                    'longitude': 0,
                    'sign': 'Unknown',
                    'degree': 0,
                    'degree_formatted': '0°0\''
                }
        
        return positions
    
    def calculate_houses(self, julian_day: float, latitude: float, longitude: float) -> List[Dict[str, any]]:
        """Calculate astrological houses."""
        try:
            # Calculate houses using Placidus system
            houses = swe.houses(julian_day, latitude, longitude, b'P')
            house_cusps = houses[0][:12]  # First 12 house cusps
            
            house_data = []
            for i, cusp in enumerate(house_cusps):
                house_data.append({
                    'house': i + 1,
                    'cusp_longitude': cusp,
                    'sign': self.get_zodiac_sign(cusp),
                    'degree': cusp % 30,
                    'degree_formatted': f"{int(cusp % 30)}°{int((cusp % 1) * 60)}'"
                })
            
            return house_data
        except Exception as e:
            print(f"Error calculating houses: {e}")
            return []
    
    def get_sun_sign(self, birth_date: datetime) -> str:
        """Get sun sign (zodiac sign) based on birth date."""
        month = birth_date.month
        day = birth_date.day
        
        # Approximate sun sign dates
        if (month == 3 and day >= 21) or (month == 4 and day <= 19):
            return "Aries"
        elif (month == 4 and day >= 20) or (month == 5 and day <= 20):
            return "Taurus"
        elif (month == 5 and day >= 21) or (month == 6 and day <= 20):
            return "Gemini"
        elif (month == 6 and day >= 21) or (month == 7 and day <= 22):
            return "Cancer"
        elif (month == 7 and day >= 23) or (month == 8 and day <= 22):
            return "Leo"
        elif (month == 8 and day >= 23) or (month == 9 and day <= 22):
            return "Virgo"
        elif (month == 9 and day >= 23) or (month == 10 and day <= 22):
            return "Libra"
        elif (month == 10 and day >= 23) or (month == 11 and day <= 21):
            return "Scorpio"
        elif (month == 11 and day >= 22) or (month == 12 and day <= 21):
            return "Sagittarius"
        elif (month == 12 and day >= 22) or (month == 1 and day <= 19):
            return "Capricorn"
        elif (month == 1 and day >= 20) or (month == 2 and day <= 18):
            return "Aquarius"
        else:
            return "Pisces"
    
    def generate_birth_chart(self, birth_date: datetime, birth_country: str) -> Dict[str, any]:
        """Generate a complete birth chart."""
        try:
            # Get coordinates
            lat, lon = self.get_coordinates(birth_country)
            
            # Calculate Julian Day
            julian_day = self.calculate_julian_day(birth_date, birth_country)
            
            # Calculate planetary positions
            planets = self.calculate_planetary_positions(julian_day)
            
            # Calculate houses
            houses = self.calculate_houses(julian_day, lat, lon)
            
            # Get basic sun sign
            sun_sign = self.get_sun_sign(birth_date)
            
            birth_chart = {
                'birth_date': birth_date.isoformat(),
                'birth_country': birth_country,
                'coordinates': {'latitude': lat, 'longitude': lon},
                'sun_sign': sun_sign,
                'planets': planets,
                'houses': houses,
                'julian_day': julian_day
            }
            
            return birth_chart
            
        except Exception as e:
            print(f"Error generating birth chart: {e}")
            # Return basic sun sign if detailed calculation fails
            return {
                'birth_date': birth_date.isoformat(),
                'birth_country': birth_country,
                'sun_sign': self.get_sun_sign(birth_date),
                'error': str(e)
            }
    
    def get_astrological_insights(self, birth_chart: Dict[str, any]) -> Dict[str, str]:
        """Generate astrological insights based on birth chart."""
        insights = {}
        
        # Basic sun sign traits
        sun_sign = birth_chart.get('sun_sign', 'Unknown')
        sun_traits = {
            'Aries': 'Dynamic, energetic, and pioneering. Natural leaders with a strong drive for action.',
            'Taurus': 'Stable, practical, and determined. Values security and enjoys life\'s pleasures.',
            'Gemini': 'Curious, adaptable, and communicative. Quick-thinking with diverse interests.',
            'Cancer': 'Nurturing, intuitive, and emotional. Strong connection to home and family.',
            'Leo': 'Confident, creative, and generous. Natural performers who enjoy being center stage.',
            'Virgo': 'Analytical, practical, and detail-oriented. Perfectionist with a desire to help others.',
            'Libra': 'Diplomatic, harmonious, and relationship-focused. Seeks balance and beauty.',
            'Scorpio': 'Intense, passionate, and transformative. Deep emotional nature with strong intuition.',
            'Sagittarius': 'Adventurous, philosophical, and optimistic. Loves freedom and exploration.',
            'Capricorn': 'Ambitious, disciplined, and responsible. Goal-oriented with strong work ethic.',
            'Aquarius': 'Independent, innovative, and humanitarian. Forward-thinking and unconventional.',
            'Pisces': 'Compassionate, intuitive, and artistic. Deeply empathetic with rich imagination.'
        }
        
        insights['sun_sign_traits'] = sun_traits.get(sun_sign, 'Unknown sign traits')
        
        # Add moon sign insights if available
        if 'planets' in birth_chart and 'Moon' in birth_chart['planets']:
            moon_sign = birth_chart['planets']['Moon']['sign']
            insights['moon_sign'] = moon_sign
            insights['emotional_nature'] = f"Your Moon in {moon_sign} influences your emotional responses and inner needs."
        
        # Add rising sign insights if available
        if 'houses' in birth_chart and birth_chart['houses']:
            rising_sign = birth_chart['houses'][0]['sign'] if birth_chart['houses'] else 'Unknown'
            insights['rising_sign'] = rising_sign
            insights['outer_personality'] = f"Your {rising_sign} rising sign shapes how others perceive you."
        
        return insights

# Global instance
astrology_service = AstrologyService()