import { create } from 'zustand'

import api from '../api/client'
import type {
  ReviewResponse,
  ReviewListResponse,
  ReviewStatus,
} from '../types'

interface ReviewFilters {
  status?: ReviewStatus | null
  ratingMax?: number | null
}

interface ReviewsState {
  reviews: ReviewResponse[]
  total: number
  page: number
  perPage: number
  filters: ReviewFilters
  isLoading: boolean
  error: string | null

  fetchReviews: (branchId: string) => Promise<void>
  setPage: (page: number) => void
  setFilters: (filters: ReviewFilters) => void
  processReview: (
    reviewId: string,
    status: 'in_progress' | 'processed',
    comment: string,
  ) => Promise<boolean>
  addReview: (review: ReviewResponse) => void
  reset: () => void
}

export const useReviewsStore = create<ReviewsState>((set, get) => ({
  reviews: [],
  total: 0,
  page: 1,
  perPage: 20,
  filters: {},
  isLoading: false,
  error: null,

  fetchReviews: async (branchId: string) => {
    const { page, perPage, filters } = get()
    set({ isLoading: true, error: null })
    try {
      const params: Record<string, string | number> = {
        page,
        per_page: perPage,
      }
      if (filters.status) params.status = filters.status
      if (filters.ratingMax) params.rating_max = filters.ratingMax

      const { data } = await api.get<ReviewListResponse>(
        `/reviews/${branchId}`,
        { params },
      )
      set({
        reviews: data.reviews,
        total: data.total,
        isLoading: false,
      })
    } catch {
      set({ error: 'Не удалось загрузить отзывы', isLoading: false })
    }
  },

  setPage: (page: number) => {
    set({ page })
  },

  setFilters: (filters: ReviewFilters) => {
    set({ filters, page: 1 })
  },

  processReview: async (
    reviewId: string,
    status: 'in_progress' | 'processed',
    comment: string,
  ): Promise<boolean> => {
    try {
      const { data } = await api.put<ReviewResponse>(
        `/reviews/${reviewId}/process`,
        { status, comment },
      )
      // Update the review in the local list
      set((state) => ({
        reviews: state.reviews.map((r) =>
          r.id === reviewId ? data : r,
        ),
      }))
      return true
    } catch {
      return false
    }
  },

  addReview: (review: ReviewResponse) => {
    set((state) => ({
      reviews: [review, ...state.reviews],
      total: state.total + 1,
    }))
  },

  reset: () => {
    set({
      reviews: [],
      total: 0,
      page: 1,
      filters: {},
      isLoading: false,
      error: null,
    })
  },
}))
