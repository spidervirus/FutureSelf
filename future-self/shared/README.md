# Database Setup for FutureSelf

This directory contains the SQL schema files needed to set up the database for the FutureSelf application.

## Quick Setup

### Option 1: Complete Setup (Recommended)

1. Open your Supabase project dashboard
2. Go to the SQL Editor
3. Copy and paste the contents of `setup_database.sql`
4. Run the script

### Option 2: Individual Table Setup

If you prefer to set up tables individually:

1. First run `users_schema.sql`
2. Then run `chat_messages_schema.sql`

## What These Scripts Do

### `setup_database.sql`
Complete database setup including:
- Creates `users` table for user profiles and preferences
- Creates `chat_messages` table for storing chat history
- Sets up Row Level Security (RLS) policies
- Creates indexes for performance
- Sets up automatic user profile creation on signup
- Includes proper foreign key relationships

### `users_schema.sql`
Creates the users table with:
- User profile information
- Communication preferences (chat/voice)
- Automatic profile creation on user signup
- RLS policies for data security

### `chat_messages_schema.sql`
Creates the chat messages table with:
- Message storage with user association
- Timestamps and metadata
- RLS policies for user data isolation
- Performance indexes

## Database Schema

### Users Table
```sql
public.users (
    id UUID PRIMARY KEY,              -- References auth.users(id)
    email TEXT,
    full_name TEXT,
    preferred_communication_method TEXT DEFAULT 'chat',
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
)
```

### Chat Messages Table
```sql
public.chat_messages (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID,                      -- References auth.users(id)
    message_id TEXT UNIQUE,            -- Unique message identifier
    content TEXT,                      -- Message content
    author_id TEXT,                    -- Author (user_id or 'future_self')
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
)
```

## Security Features

- **Row Level Security (RLS)**: Users can only access their own data
- **Foreign Key Constraints**: Ensures data integrity
- **Automatic Cleanup**: User data is deleted when auth user is deleted
- **Secure Functions**: Database functions run with appropriate permissions

## Troubleshooting

### Error: "relation 'public.chat_messages' does not exist"
This error occurs when the database tables haven't been created yet. Run the `setup_database.sql` script to resolve this.

### Error: "relation 'public.users' does not exist"
Same as above - run the setup script.

### Permission Errors
Make sure you're running the SQL scripts as a database administrator in your Supabase project.

### RLS Policy Issues
If you're having trouble with data access, check that:
1. The user is properly authenticated
2. The RLS policies are correctly applied
3. The user ID matches between `auth.users` and your application

## Testing the Setup

1. After running the setup script, try creating a new user account in your app
2. Send a test message in the chat
3. Check the Supabase dashboard to verify data is being stored correctly

## Migration Notes

If you're updating an existing database:
- The scripts use `CREATE TABLE IF NOT EXISTS` to avoid conflicts
- Existing data will be preserved
- New columns and constraints will be added safely

## Support

If you encounter issues:
1. Check the Supabase logs for detailed error messages
2. Verify your database permissions
3. Ensure your Supabase project is properly configured
4. Check that authentication is working correctly