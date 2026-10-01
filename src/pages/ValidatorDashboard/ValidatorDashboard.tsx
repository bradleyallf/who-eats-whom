import { useState, useEffect } from "react"

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api"

interface TopKPrediction {
  species: string
  common_name: string | null
  score: number
}

interface QueueRecord {
  id: number
  image_id: string
  observation_id: string
  photo_url: string
  user_species: string
  user_common_name: string | null
  ai_top1_species: string
  ai_top1_score: number
  ai_top2_score: number
  confidence_gap: number
  same_species: boolean
  topk_predictions: TopKPrediction[]
  flag_reason: string
  flag_severity: string
  pred_prey: string
  vote_count: number
  validation_status: string
}

interface QueueResponse {
  counts: {
    pending: number
    in_progress: number
    consensus: number
    no_consensus: number
  }
  results: QueueRecord[]
}

interface SessionVote {
  decision: string
  selected_species: string | null
}

function getSelectedLabel(decision: string, species: string | null, userSpecies: string): string {
  if (decision === "ai_prediction") return species || ""
  if (decision === "user_species") return userSpecies + " (user identification)"
  if (decision === "cannot_determine") return "Cannot Determine"
  return "All Incorrect"
}

function getButtonClass(base: string, active: boolean, activeClass: string, inactiveClass: string): string {
  return base + " " + (active ? activeClass : inactiveClass)
}

export const ValidatorDashboard = () => {
  const [records, setRecords] = useState<QueueRecord[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [selectedDecision, setSelectedDecision] = useState<string | null>(null)
  const [selectedSpecies, setSelectedSpecies] = useState<string | null>(null)
  const [sessionVotes, setSessionVotes] = useState<Record<number, SessionVote>>({})
  const validatorId = 1

  useEffect(() => {
    fetchQueue()
  }, [])

  useEffect(() => {
    const rec = records[currentIndex]
    if (rec) {
      const existing = sessionVotes[rec.id]
      if (existing) {
        setSelectedDecision(existing.decision)
        setSelectedSpecies(existing.selected_species)
      } else {
        setSelectedDecision(null)
        setSelectedSpecies(null)
      }
      setError(null)
      setSuccessMessage(null)
    }
  }, [currentIndex, records])

  const fetchQueue = async () => {
    setLoading(true)
    setError(null)
    try {
      const url = API_BASE + "/v1/validation/queue?limit=50&validator_id=" + String(validatorId)
      const res = await fetch(url)
      if (!res.ok) throw new Error("HTTP error " + String(res.status))
      const data = await res.json() as QueueResponse
      setRecords(data.results)
    } catch {
      setError("Failed to load validation queue. Is the backend running?")
    } finally {
      setLoading(false)
    }
  }

  const doSubmit = async (queueId: number, decision: string, species: string | null) => {
    const url = API_BASE + "/v1/validation/vote"
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        queue_id: queueId,
        validator_id: validatorId,
        decision: decision,
        selected_species: species,
      }),
    })
    return res
  }

  const doDelete = async (queueId: number) => {
    const url = API_BASE + "/v1/validation/vote/" + String(queueId) + "?validator_id=" + String(validatorId)
    const res = await fetch(url, { method: "DELETE" })
    return res
  }

  const submitVote = async () => {
    const rec = records[currentIndex]
    if (!rec || !selectedDecision) return
    setSubmitting(true)
    setError(null)
    setSuccessMessage(null)
    try {
      const res = await doSubmit(rec.id, selectedDecision, selectedSpecies)
      if (!res.ok) {
        const errData = await res.json()
        const detail = errData.detail || ""
        if (res.status === 400 && String(detail).includes("already voted")) {
          const del = await doDelete(rec.id)
          if (!del.ok) throw new Error("Failed to delete old vote")
          const res2 = await doSubmit(rec.id, selectedDecision, selectedSpecies)
          if (!res2.ok) throw new Error("Failed to resubmit vote")
          setSuccessMessage("Vote updated successfully!")
        } else {
          throw new Error(String(detail) || "Failed to submit vote")
        }
      } else {
        setSuccessMessage("Vote cast successfully!")
      }
      setSessionVotes(prev => ({
        ...prev,
        [rec.id]: { decision: selectedDecision, selected_species: selectedSpecies },
      }))
      setTimeout(() => {
        setSuccessMessage(null)
        if (currentIndex < records.length - 1) {
          setCurrentIndex(currentIndex + 1)
        }
      }, 1000)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to submit vote"
      setError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  const rec = records[currentIndex]
  const sessionVote = rec ? sessionVotes[rec.id] : null

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center space-y-4">
          <div className="text-2xl font-semibold text-slate-600">Loading validation queue...</div>
          <div className="text-slate-400">Fetching 50 records for this session</div>
        </div>
      </div>
    )
  }

  if (error && records.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center space-y-4">
          <div className="text-2xl font-semibold text-red-600">Error</div>
          <div className="text-slate-600">{error}</div>
          <button
            onClick={fetchQueue}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  if (records.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center space-y-4">
          <div className="text-2xl font-semibold text-green-600">All caught up!</div>
          <div className="text-slate-600">No flagged records remaining in the queue.</div>
        </div>
      </div>
    )
  }

  if (!rec) {
    return null
  }

  const votedCount = Object.keys(sessionVotes).length

  return (
    <div className="max-w-5xl mx-auto py-8 px-4 space-y-6">

      <div>
        <h1 className="text-3xl font-bold text-slate-800">Validator Dashboard</h1>
        <p className="text-slate-500 mt-1">Who Eats Whom - Species Identification Review</p>
      </div>

      <div className="flex justify-between text-sm text-slate-500">
        <span>{"Record " + String(currentIndex + 1) + " of " + String(records.length)}</span>
        <span>{String(votedCount) + " voted this session"}</span>
      </div>

      {successMessage && (
        <div className="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded">
          {successMessage}
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

        <div className="space-y-4">

          <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
            <img
              src={rec.photo_url}
              alt={rec.user_species}
              className="w-full object-cover"
              style={{ maxHeight: "350px" }}
              onError={(e) => {
                const t = e.target as HTMLImageElement
                if (t.src.endsWith(".jpeg")) {
                  t.src = t.src.replace(".jpeg", ".jpg")
                } else if (t.src.endsWith(".jpg")) {
                  t.src = t.src.replace(".jpg", ".png")
                } else {
                  t.src = "https://via.placeholder.com/400x300?text=Image+not+available"
                }
              }}
            />
          </div>

          <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-3">
            <h3 className="font-semibold text-slate-700">Observation</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-500">Observation ID</span>
                <span className="font-mono">{rec.observation_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Votes so far</span>
                <span>{String(rec.vote_count) + " / 3"}</span>
              </div>
              {sessionVote && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Your vote</span>
                  <span className="text-blue-600 font-medium">
                    {sessionVote.selected_species || sessionVote.decision}
                  </span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-slate-500">iNaturalist</span>
                
                  href={"https://www.inaturalist.org/observations/" + rec.observation_id}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline"
                >
                  View original
                </a>
              </div>
            </div>
          </div>

        </div>

        <div className="space-y-4">

          <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-3">
            <h3 className="font-semibold text-slate-700">Species Identification</h3>

            <div className="bg-blue-50 border border-blue-200 rounded p-3">
              <div className="text-xs text-blue-600 font-medium uppercase tracking-wide mb-1">
                iNaturalist User Identified
              </div>
              <div className="font-semibold text-slate-800 italic">
                {rec.user_species}
              </div>
              {rec.user_common_name && (
                <div className="text-sm text-slate-500">{rec.user_common_name}</div>
              )}
            </div>

            <div className="space-y-2">
              <div className="text-xs text-slate-500 font-medium uppercase tracking-wide">
                AI Top 5 Predictions (BioCLIP2)
              </div>
              {rec.topk_predictions.map((pred, idx) => (
                <div
                  key={idx}
                  className={
                    "border rounded p-2 flex items-center justify-between " +
                    (idx === 0 ? "border-orange-300 bg-orange-50" : "border-slate-200 bg-slate-50")
                  }
                >
                  <div>
                    <div className="flex items-center gap-2">
                      {idx === 0 && (
                        <span className="text-xs bg-orange-200 text-orange-800 px-1.5 py-0.5 rounded font-medium">
                          TOP
                        </span>
                      )}
                      <span className="font-medium italic text-sm">{pred.species}</span>
                    </div>
                    {pred.common_name && (
                      <div className="text-xs text-slate-500">{pred.common_name}</div>
                    )}
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-semibold text-slate-700">
                      {(pred.score * 100).toFixed(1) + "%"}
                    </div>
                    <div className="w-16 bg-slate-200 rounded-full h-1.5 mt-1">
                      <div
                        className="bg-orange-400 h-1.5 rounded-full"
                        style={{ width: Math.min(pred.score * 100, 100).toFixed(1) + "%" }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-3">

            <h3 className="font-semibold text-slate-700">
              {"Your Decision"}
              {sessionVote && (
                <span className="ml-2 text-xs text-blue-600 font-normal">
                  (previously voted - select to overwrite)
                </span>
              )}
            </h3>

            <p className="text-xs text-slate-500">Select an option then click Cast Vote.</p>

            <div className="space-y-2">
              <div className="text-xs text-slate-500 font-medium">AI Predictions:</div>
              {rec.topk_predictions.map((pred, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setSelectedDecision("ai_prediction")
                    setSelectedSpecies(pred.species)
                  }}
                  className={getButtonClass(
                    "w-full text-left px-3 py-2 border rounded transition-colors",
                    selectedDecision === "ai_prediction" && selectedSpecies === pred.species,
                    "border-orange-500 bg-orange-100",
                    "border-slate-200 hover:bg-orange-50 hover:border-orange-300"
                  )}
                >
                  <div className="flex justify-between items-center">
                    <span className="text-sm italic">{pred.species}</span>
                    <span className="text-xs text-slate-500">
                      {(pred.score * 100).toFixed(1) + "%"}
                    </span>
                  </div>
                  {pred.common_name && (
                    <div className="text-xs text-slate-400">{pred.common_name}</div>
                  )}
                </button>
              ))}
            </div>

            <div className="space-y-2">
              <div className="text-xs text-slate-500 font-medium">Original identification:</div>
              <button
                onClick={() => {
                  setSelectedDecision("user_species")
                  setSelectedSpecies(rec.user_species)
                }}
                className={getButtonClass(
                  "w-full text-left px-3 py-2 border rounded transition-colors",
                  selectedDecision === "user_species",
                  "border-blue-500 bg-blue-100",
                  "border-blue-200 bg-blue-50 hover:bg-blue-100"
                )}
              >
                <div className="text-sm italic font-medium text-blue-800">{rec.user_species}</div>
                <div className="text-xs text-blue-600">iNaturalist user identification</div>
              </button>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => {
                  setSelectedDecision("cannot_determine")
                  setSelectedSpecies(null)
                }}
                className={getButtonClass(
                  "px-3 py-2 border rounded transition-colors text-sm",
                  selectedDecision === "cannot_determine",
                  "border-slate-500 bg-slate-100 text-slate-800",
                  "border-slate-300 hover:bg-slate-50 text-slate-600"
                )}
              >
                Cannot Determine
              </button>
              <button
                onClick={() => {
                  setSelectedDecision("all_incorrect")
                  setSelectedSpecies(null)
                }}
                className={getButtonClass(
                  "px-3 py-2 border rounded transition-colors text-sm",
                  selectedDecision === "all_incorrect",
                  "border-red-500 bg-red-100 text-red-800",
                  "border-red-200 hover:bg-red-50 text-red-600"
                )}
              >
                All Incorrect
              </button>
            </div>

            {selectedDecision && (
              <div className="bg-slate-50 border border-slate-200 rounded p-2 text-sm">
                <span className="text-slate-500">Selected: </span>
                <span className="font-medium">
                  {getSelectedLabel(selectedDecision, selectedSpecies, rec.user_species)}
                </span>
              </div>
            )}

            <button
              onClick={submitVote}
              disabled={!selectedDecision || submitting}
              className="w-full py-3 bg-blue-600 text-white rounded font-semibold hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? "Submitting..." : sessionVote ? "Update Vote" : "Cast Vote"}
            </button>

          </div>

          <div className="flex justify-between">
            <button
              onClick={() => setCurrentIndex(Math.max(0, currentIndex - 1))}
              disabled={currentIndex === 0}
              className="px-4 py-2 border border-slate-200 rounded hover:bg-slate-50 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <button
              onClick={() => setCurrentIndex(Math.min(records.length - 1, currentIndex + 1))}
              disabled={currentIndex === records.length - 1}
              className="px-4 py-2 border border-slate-200 rounded hover:bg-slate-50 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>

        </div>
      </div>
    </div>
  )
}