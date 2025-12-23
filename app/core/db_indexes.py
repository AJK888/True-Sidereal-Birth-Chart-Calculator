"""
Database Index Management

Defines and manages database indexes for query optimization.
"""

from sqlalchemy import Index
from database import User, SavedChart, ChatConversation, ChatMessage, CreditTransaction


# Index definitions for query optimization
# These should be added via Alembic migrations

# User indexes
user_email_index = Index('idx_user_email', User.email)
user_created_at_index = Index('idx_user_created_at', User.created_at)
user_subscription_status_index = Index('idx_user_subscription_status', User.subscription_status)
user_is_active_index = Index('idx_user_is_active', User.is_active)
user_stripe_customer_index = Index('idx_user_stripe_customer', User.stripe_customer_id)

# SavedChart indexes
chart_user_id_index = Index('idx_chart_user_id', SavedChart.user_id)
chart_created_at_index = Index('idx_chart_created_at', SavedChart.created_at)
chart_birth_year_index = Index('idx_chart_birth_year', SavedChart.birth_year)
chart_birth_month_index = Index('idx_chart_birth_month', SavedChart.birth_month)
# Composite index for common queries
chart_user_created_index = Index('idx_chart_user_created', SavedChart.user_id, SavedChart.created_at)

# ChatConversation indexes
conversation_user_id_index = Index('idx_conversation_user_id', ChatConversation.user_id)
conversation_chart_id_index = Index('idx_conversation_chart_id', ChatConversation.chart_id)
conversation_created_at_index = Index('idx_conversation_created_at', ChatConversation.created_at)
# Composite index for user's conversations
conversation_user_created_index = Index('idx_conversation_user_created', ChatConversation.user_id, ChatConversation.created_at)

# ChatMessage indexes
message_conversation_id_index = Index('idx_message_conversation_id', ChatMessage.conversation_id)
message_created_at_index = Index('idx_message_created_at', ChatMessage.created_at)
message_sequence_index = Index('idx_message_sequence', ChatMessage.conversation_id, ChatMessage.sequence_number)

# CreditTransaction indexes
transaction_user_id_index = Index('idx_transaction_user_id', CreditTransaction.user_id)
transaction_type_index = Index('idx_transaction_type', CreditTransaction.transaction_type)
transaction_created_at_index = Index('idx_transaction_created_at', CreditTransaction.created_at)
# Composite index for user transaction queries
transaction_user_created_index = Index('idx_transaction_user_created', CreditTransaction.user_id, CreditTransaction.created_at)


# List of all indexes for easy reference
ALL_INDEXES = [
    user_email_index,
    user_created_at_index,
    user_subscription_status_index,
    user_is_active_index,
    user_stripe_customer_index,
    chart_user_id_index,
    chart_created_at_index,
    chart_birth_year_index,
    chart_birth_month_index,
    chart_user_created_index,
    conversation_user_id_index,
    conversation_chart_id_index,
    conversation_created_at_index,
    conversation_user_created_index,
    message_conversation_id_index,
    message_created_at_index,
    message_sequence_index,
    transaction_user_id_index,
    transaction_type_index,
    transaction_created_at_index,
    transaction_user_created_index,
]


def get_index_creation_sql():
    """Generate SQL statements for creating indexes."""
    # This would be used in Alembic migrations
    # For now, return a list of index names
    return [
        "CREATE INDEX IF NOT EXISTS idx_user_email ON users(email);",
        "CREATE INDEX IF NOT EXISTS idx_user_created_at ON users(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_user_subscription_status ON users(subscription_status);",
        "CREATE INDEX IF NOT EXISTS idx_user_is_active ON users(is_active);",
        "CREATE INDEX IF NOT EXISTS idx_user_stripe_customer ON users(stripe_customer_id);",
        "CREATE INDEX IF NOT EXISTS idx_chart_user_id ON saved_charts(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_chart_created_at ON saved_charts(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_chart_birth_year ON saved_charts(birth_year);",
        "CREATE INDEX IF NOT EXISTS idx_chart_birth_month ON saved_charts(birth_month);",
        "CREATE INDEX IF NOT EXISTS idx_chart_user_created ON saved_charts(user_id, created_at);",
        "CREATE INDEX IF NOT EXISTS idx_conversation_user_id ON chat_conversations(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_conversation_chart_id ON chat_conversations(chart_id);",
        "CREATE INDEX IF NOT EXISTS idx_conversation_created_at ON chat_conversations(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_conversation_user_created ON chat_conversations(user_id, created_at);",
        "CREATE INDEX IF NOT EXISTS idx_message_conversation_id ON chat_messages(conversation_id);",
        "CREATE INDEX IF NOT EXISTS idx_message_created_at ON chat_messages(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_message_sequence ON chat_messages(conversation_id, sequence_number);",
        "CREATE INDEX IF NOT EXISTS idx_transaction_user_id ON credit_transactions(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_transaction_type ON credit_transactions(transaction_type);",
        "CREATE INDEX IF NOT EXISTS idx_transaction_created_at ON credit_transactions(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_transaction_user_created ON credit_transactions(user_id, created_at);",
    ]

