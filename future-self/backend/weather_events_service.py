#!/usr/bin/env python3

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import os
from dataclasses import dataclass

@dataclass
class WeatherData:
    """Weather data structure"""
    temperature: float
    feels_like: float
    humidity: int
    description: str
    wind_speed: float
    pressure: float
    uv_index: Optional[float] = None
    visibility: Optional[float] = None

@dataclass
class EventData:
    """Event data structure"""
    name: str
    date: str
    venue: str
    category: str
    url: Optional[str] = None
    description: Optional[str] = None

class WeatherEventsService:
    """Service for fetching weather and events data for location-based context"""
    
    def __init__(self):
        # API Keys - should be set as environment variables
        self.openweather_api_key = os.getenv('OPENWEATHERMAP_API_KEY', 'your_openweather_api_key')
        self.ticketmaster_api_key = os.getenv('TICKETMASTER_API_KEY', 'your_ticketmaster_api_key')
        
        # API Base URLs
        self.openweather_base_url = "https://api.openweathermap.org/data/2.5"
        self.ticketmaster_base_url = "https://app.ticketmaster.com/discovery/v2"
        
        # Default parameters
        self.default_radius = "25"  # miles for events search
        self.default_event_size = "20"  # number of events to fetch
    
    def get_coordinates_from_location(self, location: str) -> Optional[Dict[str, float]]:
        """Get latitude and longitude from location name using OpenWeather Geocoding API"""
        try:
            geocoding_url = f"http://api.openweathermap.org/geo/1.0/direct"
            params = {
                'q': location,
                'limit': 1,
                'appid': self.openweather_api_key
            }
            
            response = requests.get(geocoding_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data:
                return {
                    'lat': data[0]['lat'],
                    'lon': data[0]['lon']
                }
            return None
            
        except Exception as e:
            print(f"Error getting coordinates for {location}: {e}")
            return None
    
    def get_current_weather(self, lat: float, lon: float) -> Optional[WeatherData]:
        """Get current weather data for given coordinates"""
        try:
            url = f"{self.openweather_base_url}/weather"
            params = {
                'lat': lat,
                'lon': lon,
                'appid': self.openweather_api_key,
                'units': 'metric'  # Celsius
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            return WeatherData(
                temperature=data['main']['temp'],
                feels_like=data['main']['feels_like'],
                humidity=data['main']['humidity'],
                description=data['weather'][0]['description'],
                wind_speed=data['wind']['speed'],
                pressure=data['main']['pressure'],
                visibility=data.get('visibility', 0) / 1000 if 'visibility' in data else None  # Convert to km
            )
            
        except Exception as e:
            print(f"Error fetching weather data: {e}")
            return None
    
    def get_weather_forecast(self, lat: float, lon: float, days: int = 5) -> List[Dict[str, Any]]:
        """Get weather forecast for the next few days"""
        try:
            url = f"{self.openweather_base_url}/forecast"
            params = {
                'lat': lat,
                'lon': lon,
                'appid': self.openweather_api_key,
                'units': 'metric',
                'cnt': days * 8  # 8 forecasts per day (3-hour intervals)
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            forecasts = []
            
            for item in data['list']:
                forecasts.append({
                    'datetime': item['dt_txt'],
                    'temperature': item['main']['temp'],
                    'description': item['weather'][0]['description'],
                    'humidity': item['main']['humidity'],
                    'wind_speed': item['wind']['speed']
                })
            
            return forecasts
            
        except Exception as e:
            print(f"Error fetching weather forecast: {e}")
            return []
    
    def get_local_events(self, lat: float, lon: float, radius: str = None, size: str = None) -> List[EventData]:
        """Get local events using Ticketmaster Discovery API"""
        try:
            url = f"{self.ticketmaster_base_url}/events.json"
            params = {
                'apikey': self.ticketmaster_api_key,
                'latlong': f"{lat},{lon}",
                'radius': radius or self.default_radius,
                'unit': 'miles',
                'size': size or self.default_event_size,
                'sort': 'date,asc'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            events = []
            
            if '_embedded' in data and 'events' in data['_embedded']:
                for event in data['_embedded']['events']:
                    # Extract venue information
                    venue_name = "Unknown Venue"
                    if '_embedded' in event and 'venues' in event['_embedded']:
                        venue_name = event['_embedded']['venues'][0].get('name', 'Unknown Venue')
                    
                    # Extract category/genre
                    category = "General"
                    if 'classifications' in event and event['classifications']:
                        classification = event['classifications'][0]
                        if 'segment' in classification:
                            category = classification['segment'].get('name', 'General')
                    
                    events.append(EventData(
                        name=event.get('name', 'Unknown Event'),
                        date=event['dates']['start'].get('localDate', 'TBD'),
                        venue=venue_name,
                        category=category,
                        url=event.get('url'),
                        description=event.get('info', '')
                    ))
            
            return events
            
        except Exception as e:
            print(f"Error fetching events data: {e}")
            return []
    
    async def get_location_context(self, location: str) -> Dict[str, Any]:
        """Get comprehensive location context including weather and events"""
        context = {
            'location': location,
            'weather': None,
            'forecast': [],
            'events': [],
            'context_summary': '',
            'timestamp': datetime.now().isoformat()
        }
        
        # Get coordinates
        coords = self.get_coordinates_from_location(location)
        if not coords:
            context['context_summary'] = f"Could not find location: {location}"
            return context
        
        lat, lon = coords['lat'], coords['lon']
        
        # Get current weather
        weather = self.get_current_weather(lat, lon)
        if weather:
            context['weather'] = {
                'temperature': weather.temperature,
                'feels_like': weather.feels_like,
                'humidity': weather.humidity,
                'description': weather.description,
                'wind_speed': weather.wind_speed,
                'pressure': weather.pressure,
                'visibility': weather.visibility
            }
        
        # Get weather forecast
        context['forecast'] = self.get_weather_forecast(lat, lon, days=3)
        
        # Get local events
        events = self.get_local_events(lat, lon)
        context['events'] = [
            {
                'name': event.name,
                'date': event.date,
                'venue': event.venue,
                'category': event.category,
                'url': event.url
            } for event in events[:10]  # Limit to 10 events
        ]
        
        # Generate context summary
        context['context_summary'] = self._generate_context_summary(weather, events, location)
        
        return context
    
    def _generate_context_summary(self, weather: Optional[WeatherData], events: List[EventData], location: str) -> str:
        """Generate a human-readable context summary"""
        summary_parts = []
        
        if weather:
            summary_parts.append(
                f"Current weather in {location}: {weather.description} with temperature {weather.temperature}°C "
                f"(feels like {weather.feels_like}°C), humidity {weather.humidity}%, wind speed {weather.wind_speed} m/s."
            )
        
        if events:
            upcoming_events = [e for e in events if e.date and e.date != 'TBD']
            if upcoming_events:
                event_categories = list(set([e.category for e in upcoming_events[:5]]))
                summary_parts.append(
                    f"Upcoming local events include {', '.join(event_categories)} events. "
                    f"Notable events: {', '.join([e.name for e in upcoming_events[:3]])}."
                )
        
        return ' '.join(summary_parts) if summary_parts else f"Location context for {location} is currently unavailable."
    
    def get_weather_advice(self, weather: Optional[WeatherData]) -> str:
        """Generate weather-based advice"""
        if not weather:
            return "Weather information is not available for personalized advice."
        
        advice = []
        
        # Temperature advice
        if weather.temperature < 0:
            advice.append("It's freezing outside - dress warmly and consider indoor activities.")
        elif weather.temperature < 10:
            advice.append("It's quite cold - layer up and maybe enjoy a warm drink.")
        elif weather.temperature > 30:
            advice.append("It's very hot - stay hydrated and seek shade when possible.")
        elif weather.temperature > 25:
            advice.append("It's warm and pleasant - great weather for outdoor activities.")
        
        # Humidity advice
        if weather.humidity > 80:
            advice.append("High humidity might make it feel more uncomfortable.")
        elif weather.humidity < 30:
            advice.append("Low humidity - consider staying hydrated.")
        
        # Wind advice
        if weather.wind_speed > 10:
            advice.append("It's quite windy - secure loose items and dress accordingly.")
        
        # Weather condition advice
        if 'rain' in weather.description.lower():
            advice.append("Don't forget an umbrella or raincoat.")
        elif 'snow' in weather.description.lower():
            advice.append("Snow is expected - drive carefully and dress warmly.")
        elif 'clear' in weather.description.lower() or 'sunny' in weather.description.lower():
            advice.append("Clear skies - perfect for outdoor plans.")
        
        return ' '.join(advice) if advice else "Weather conditions are moderate - enjoy your day!"

# Create a global instance
weather_events_service = WeatherEventsService()