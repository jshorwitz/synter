'use client';

import React, { useState } from 'react';

interface StripePaymentProps {
  amount: number;
  onSuccess: (result: any) => void;
  onError: (error: string) => void;
}

export default function StripePayment({ amount, onSuccess, onError }: StripePaymentProps) {
  const [loading, setLoading] = useState(false);
  const [cardholderName, setCardholderName] = useState('');
  const [email, setEmail] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Create checkout session for Stripe
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}/api/v1/billing/create-checkout-session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: 'credit_pack',
          product_id: `credits_${Math.ceil(amount / 100)}`, // Convert cents to dollars for product ID
          workspace_id: 'default-workspace', // TODO: Get from auth context
          success_url: window.location.origin + '/settings/billing?success=true',
          cancel_url: window.location.origin + '/settings/billing?canceled=true'
        })
      });

      if (response.ok) {
        const result = await response.json();
        // Redirect to Stripe Checkout
        if (result.checkout_url) {
          window.location.href = result.checkout_url;
        } else {
          onSuccess(result);
        }
      } else {
        const errorData = await response.json();
        onError(errorData.detail || errorData.error || 'Payment failed');
      }
    } catch (err) {
      onError('Payment failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto bg-white p-6 rounded-lg shadow">
      <h3 className="text-lg font-medium text-gray-900 mb-4">
        Purchase ${amount} in credits
      </h3>
      
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Email
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="block w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Cardholder Name
          </label>
          <input
            type="text"
            value={cardholderName}
            onChange={(e) => setCardholderName(e.target.value)}
            required
            className="block w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Card Details
          </label>
          <div className="border border-gray-300 rounded-md p-3 bg-gray-50">
            <p className="text-sm text-gray-600">
              In production, this would be replaced with Stripe Elements for secure card input.
            </p>
            <p className="text-xs text-gray-500 mt-1">
              Test card: 4242 4242 4242 4242
            </p>
          </div>
        </div>

        <button
          type="submit"
          disabled={loading || !email || !cardholderName}
          className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Processing...' : `Pay $${amount}`}
        </button>
      </form>

      <div className="mt-4 text-xs text-gray-500">
        <p>🔒 Your payment information is secure and encrypted.</p>
        <p className="mt-1">
          This is a demo interface. In production, card details would be handled 
          securely by Stripe Elements.
        </p>
      </div>
    </div>
  );
}
