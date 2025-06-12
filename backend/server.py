from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import httpx
import json
from datetime import datetime, timedelta
import uuid
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
from emergentintegrations.llm.chat import LlmChat, UserMessage

app = FastAPI(title="PlanMyDay API")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(MONGO_URL)
db = client.planmyday
venues_collection = db.venues
plans_collection = db.day_plans
users_collection = db.users

# API Keys
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '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')
WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY', 'b6b0b1e2a307b8626098a982fc28bb6b')

# Models
class Location(BaseModel):
    lat: float
    lng: float
    address: str

class PlanRequest(BaseModel):
    location: Location
    budget: int
    interests: List[str]
    duration: str  # "half-day", "full-day"
    group_size: int = 1

class Venue(BaseModel):
    id: str
    name: str
    category: str  # restaurant, activity, event, attraction
    location: Location
    price_range: str  # $, $$, $$$, $$$$
    rating: float
    description: str
    popular_items: List[str] = []
    opening_hours: str
    estimated_duration: int  # minutes
    booking_url: Optional[str] = None

class WeatherData(BaseModel):
    temperature: float
    description: str
    feels_like: float
    humidity: int
    weather_main: str

class ItineraryItem(BaseModel):
    venue: Venue
    start_time: str
    end_time: str
    travel_time_to_next: int = 0
    notes: str = ""

class DayPlan(BaseModel):
    id: str
    location: Location
    date: str
    weather: WeatherData
    total_budget: int
    estimated_cost: int
    itinerary: List[ItineraryItem]
    created_at: datetime

# Sample venue data
SAMPLE_VENUES = [
    {
        "id": str(uuid.uuid4()),
        "name": "The Coffee Corner",
        "category": "restaurant",
        "location": {"lat": 40.7589, "lng": -73.9851, "address": "123 Broadway, NYC"},
        "price_range": "$$",
        "rating": 4.5,
        "description": "Cozy coffee shop with artisanal pastries and light breakfast",
        "popular_items": ["Cappuccino", "Croissant", "Avocado Toast"],
        "opening_hours": "7:00 AM - 6:00 PM",
        "estimated_duration": 45,
        "booking_url": "https://example.com/book"
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Central Park",
        "category": "attraction",
        "location": {"lat": 40.7821, "lng": -73.9654, "address": "Central Park, NYC"},
        "price_range": "$",
        "rating": 4.8,
        "description": "Iconic urban park perfect for walking, picnics, and recreation",
        "popular_items": ["Walking paths", "Bethesda Fountain", "Strawberry Fields"],
        "opening_hours": "6:00 AM - 1:00 AM",
        "estimated_duration": 120,
        "booking_url": None
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Metropolitan Museum",
        "category": "attraction",
        "location": {"lat": 40.7794, "lng": -73.9632, "address": "1000 5th Ave, NYC"},
        "price_range": "$$$",
        "rating": 4.7,
        "description": "World-class art museum with extensive collections",
        "popular_items": ["Egyptian Art", "European Paintings", "Arms & Armor"],
        "opening_hours": "10:00 AM - 5:00 PM",
        "estimated_duration": 180,
        "booking_url": "https://metmuseum.org/visit"
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Joe's Pizza",
        "category": "restaurant",
        "location": {"lat": 40.7505, "lng": -73.9934, "address": "456 8th Ave, NYC"},
        "price_range": "$",
        "rating": 4.3,
        "description": "Authentic NYC pizza joint with classic thin crust slices",
        "popular_items": ["Cheese Pizza", "Pepperoni", "Sicilian Slice"],
        "opening_hours": "11:00 AM - 11:00 PM",
        "estimated_duration": 30,
        "booking_url": None
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Broadway Theater District",
        "category": "activity",
        "location": {"lat": 40.7590, "lng": -73.9845, "address": "Times Square, NYC"},
        "price_range": "$$$$",
        "rating": 4.6,
        "description": "Catch a world-class Broadway show in the theater district",
        "popular_items": ["Lion King", "Hamilton", "Phantom of the Opera"],
        "opening_hours": "Various show times",
        "estimated_duration": 180,
        "booking_url": "https://broadway.com"
    },
    {
        "id": str(uuid.uuid4()),
        "name": "High Line Park",
        "category": "attraction",
        "location": {"lat": 40.7480, "lng": -74.0048, "address": "High Line, NYC"},
        "price_range": "$",
        "rating": 4.5,
        "description": "Elevated linear park built on former railway tracks",
        "popular_items": ["Walking trail", "City views", "Art installations"],
        "opening_hours": "7:00 AM - 7:00 PM",
        "estimated_duration": 90,
        "booking_url": None
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Eataly NYC",
        "category": "restaurant",
        "location": {"lat": 40.7424, "lng": -73.9899, "address": "200 5th Ave, NYC"},
        "price_range": "$$$",
        "rating": 4.4,
        "description": "Italian marketplace with restaurants, cafes, and gourmet products",
        "popular_items": ["Fresh Pasta", "Gelato", "Italian Wine"],
        "opening_hours": "10:00 AM - 11:00 PM",
        "estimated_duration": 75,
        "booking_url": "https://eataly.com"
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Brooklyn Bridge",
        "category": "attraction",
        "location": {"lat": 40.7061, "lng": -73.9969, "address": "Brooklyn Bridge, NYC"},
        "price_range": "$",
        "rating": 4.6,
        "description": "Historic suspension bridge with stunning city views",
        "popular_items": ["Walking path", "Photography spots", "City skyline views"],
        "opening_hours": "24 hours",
        "estimated_duration": 60,
        "booking_url": None
    }
]

async def init_sample_data():
    """Initialize sample venue data"""
    try:
        count = await venues_collection.count_documents({})
        if count == 0:
            await venues_collection.insert_many(SAMPLE_VENUES)
            print("Sample venues initialized")
    except Exception as e:
        print(f"Error initializing sample data: {e}")

@app.on_event("startup")
async def startup_event():
    await init_sample_data()

class WeatherService:
    @staticmethod
    async def get_current_weather(lat: float, lng: float) -> WeatherData:
        """Get current weather data"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://api.openweathermap.org/data/2.5/weather",
                    params={
                        "lat": lat,
                        "lon": lng,
                        "appid": WEATHER_API_KEY,
                        "units": "metric"
                    },
                    timeout=10
                )
                response.raise_for_status()
                data = response.json()
                
                return WeatherData(
                    temperature=data["main"]["temp"],
                    description=data["weather"][0]["description"],
                    feels_like=data["main"]["feels_like"],
                    humidity=data["main"]["humidity"],
                    weather_main=data["weather"][0]["main"]
                )
        except Exception as e:
            # Fallback weather data
            return WeatherData(
                temperature=22.0,
                description="partly cloudy",
                feels_like=24.0,
                humidity=65,
                weather_main="Clouds"
            )

class AIPlanner:
    @staticmethod
    async def generate_itinerary(request: PlanRequest, weather: WeatherData, venues: List[Dict]) -> List[ItineraryItem]:
        """Generate AI-powered itinerary"""
        try:
            chat = LlmChat(
                api_key=OPENAI_API_KEY,
                session_id=str(uuid.uuid4()),
                system_message="You are an expert day planner. Create optimized itineraries based on user preferences, weather, and available venues."
            ).with_model("openai", "gpt-4o")
            
            venue_info = "\n".join([
                f"- {v['name']} ({v['category']}): {v['description']} - {v['price_range']} - Duration: {v['estimated_duration']}min"
                for v in venues[:15]  # Limit for context
            ])
            
            weather_context = f"Weather: {weather.temperature}°C, {weather.description}"
            if weather.weather_main.lower() in ['rain', 'thunderstorm']:
                weather_context += " (Suggest more indoor activities)"
            elif weather.temperature > 25:
                weather_context += " (Great for outdoor activities)"
            
            prompt = f"""
            Create a detailed day plan with the following requirements:
            
            Location: {request.location.address}
            Budget: ${request.budget}
            Duration: {request.duration}
            Interests: {', '.join(request.interests)}
            Group Size: {request.group_size}
            {weather_context}
            
            Available venues:
            {venue_info}
            
            Please provide a JSON response with this exact structure:
            {{
                "itinerary": [
                    {{
                        "venue_name": "venue name",
                        "start_time": "HH:MM",
                        "end_time": "HH:MM",
                        "notes": "why this fits the plan"
                    }}
                ]
            }}
            
            Rules:
            - Start after 8:00 AM, consider venue opening hours
            - Include 2-3 restaurants and 3-5 activities/attractions
            - Factor in travel time between locations
            - Stay within budget
            - Consider weather for indoor/outdoor balance
            - Optimize for user interests
            """
            
            user_message = UserMessage(text=prompt)
            response = await chat.send_message(user_message)
            
            # Parse AI response
            try:
                ai_data = json.loads(response)
                itinerary_items = []
                
                for item in ai_data.get("itinerary", []):
                    # Find matching venue
                    venue_match = next(
                        (v for v in venues if v["name"].lower() in item["venue_name"].lower()),
                        None
                    )
                    
                    if venue_match:
                        venue_obj = Venue(**venue_match)
                        itinerary_items.append(ItineraryItem(
                            venue=venue_obj,
                            start_time=item["start_time"],
                            end_time=item["end_time"],
                            notes=item.get("notes", "")
                        ))
                
                return itinerary_items
                
            except json.JSONDecodeError:
                # Fallback to rule-based planning
                return await AIPlanner.fallback_planning(request, weather, venues)
                
        except Exception as e:
            print(f"AI planning error: {e}")
            return await AIPlanner.fallback_planning(request, weather, venues)
    
    @staticmethod
    async def fallback_planning(request: PlanRequest, weather: WeatherData, venues: List[Dict]) -> List[ItineraryItem]:
        """Fallback rule-based planning"""
        suitable_venues = []
        
        # Filter venues based on interests and weather
        for venue in venues:
            if weather.weather_main.lower() in ['rain', 'thunderstorm']:
                if venue['category'] in ['restaurant', 'activity'] or 'museum' in venue['name'].lower():
                    suitable_venues.append(venue)
            else:
                suitable_venues.append(venue)
        
        # Sort by rating and select top venues
        suitable_venues.sort(key=lambda x: x['rating'], reverse=True)
        selected_venues = suitable_venues[:6]
        
        # Create simple itinerary
        itinerary = []
        current_time = datetime.strptime("09:00", "%H:%M")
        
        for venue in selected_venues:
            venue_obj = Venue(**venue)
            start_time = current_time.strftime("%H:%M")
            end_time = (current_time + timedelta(minutes=venue['estimated_duration'])).strftime("%H:%M")
            
            itinerary.append(ItineraryItem(
                venue=venue_obj,
                start_time=start_time,
                end_time=end_time,
                notes=f"Perfect for {', '.join(request.interests)}"
            ))
            
            current_time += timedelta(minutes=venue['estimated_duration'] + 30)  # Add travel time
        
        return itinerary

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/venues")
async def get_venues():
    """Get all available venues"""
    venues = await venues_collection.find({}).to_list(100)
    for venue in venues:
        venue["_id"] = str(venue["_id"])
    return {"venues": venues}

@app.post("/api/plan")
async def create_day_plan(request: PlanRequest):
    """Generate AI-powered day plan"""
    try:
        # Get weather data
        weather = await WeatherService.get_current_weather(request.location.lat, request.location.lng)
        
        # Get available venues
        venues_cursor = venues_collection.find({})
        venues = await venues_cursor.to_list(100)
        
        # Generate AI itinerary
        itinerary = await AIPlanner.generate_itinerary(request, weather, venues)
        
        # Calculate estimated cost
        estimated_cost = sum([
            25 if item.venue.price_range == "$" else
            50 if item.venue.price_range == "$$" else
            100 if item.venue.price_range == "$$$" else 150
            for item in itinerary
        ])
        
        # Create day plan
        day_plan = DayPlan(
            id=str(uuid.uuid4()),
            location=request.location,
            date=datetime.now().strftime("%Y-%m-%d"),
            weather=weather,
            total_budget=request.budget,
            estimated_cost=estimated_cost,
            itinerary=itinerary,
            created_at=datetime.now()
        )
        
        # Save to database
        await plans_collection.insert_one(day_plan.dict())
        
        return day_plan
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create day plan: {str(e)}")

@app.get("/api/plans/{plan_id}")
async def get_plan(plan_id: str):
    """Get specific day plan"""
    plan = await plans_collection.find_one({"id": plan_id})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    plan["_id"] = str(plan["_id"])
    return plan

@app.get("/api/weather")
async def get_weather(lat: float, lng: float):
    """Get current weather"""
    weather = await WeatherService.get_current_weather(lat, lng)
    return weather

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)