/**
 * AI Image Creator UI Integration Example
 * 
 * This file demonstrates how to integrate with the backend API endpoints
 * to create a UI similar to the AI Image Creator cards shown in the image.
 */

// Configuration
const API_BASE_URL = '/api/search';

/**
 * Search for AI image creation tools and display results in UI
 * @param {string} query - The search query text
 */
async function searchAIImageTools(query) {
    try {
        // Show loading state
        showLoadingState();
        
        // First, get the summary and structured data
        const response = await fetch(`${API_BASE_URL}/search-with-summary`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: query
            })
        });
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }
        
        // Parse response
        const data = await response.json();
        
        // Display the summary first (can be used in chat or as header)
        displaySummary(data.summary);
        
        // Display the structured results in the AI Image Creator UI
        displayImageCreatorCards(data.formatted_results);
        
        // Store the raw results for advanced use cases
        storeRawResults(data.raw_results);
        
    } catch (error) {
        console.error('Error searching for AI image tools:', error);
        displayError(error.message);
    } finally {
        // Hide loading state
        hideLoadingState();
    }
}

/**
 * Get detailed information about a specific tool by its objectID
 * @param {string} objectId - The Algolia objectID of the tool
 * @returns {Promise<object>} - The tool details
 */
async function getToolDetails(objectId) {
    try {
        const response = await fetch(`${API_BASE_URL}/object/${objectId}`);
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error(`Error fetching tool details for ${objectId}:`, error);
        throw error;
    }
}

/**
 * Display the search summary
 * @param {string} summary - The text summary of search results
 */
function displaySummary(summary) {
    const summaryElement = document.getElementById('search-summary');
    if (summaryElement) {
        summaryElement.innerHTML = summary.replace(/\n/g, '<br>');
        summaryElement.style.display = 'block';
    }
}

/**
 * Store raw search results for advanced use cases
 * @param {object} rawResults - The complete search results from the API
 */
function storeRawResults(rawResults) {
    // Store the raw results in a global variable or data attribute
    // This can be used for advanced filtering, sorting, or other operations
    window.rawSearchResults = rawResults;
    
    // Optionally display raw results in a debug panel
    const rawResultsElement = document.getElementById('raw-results');
    if (rawResultsElement) {
        // Format the JSON nicely
        const formattedJson = JSON.stringify(rawResults, null, 2);
        
        // Create a collapsible section for raw results
        rawResultsElement.innerHTML = `
            <details>
                <summary>Raw Search Results (Click to expand)</summary>
                <pre>${formattedJson}</pre>
            </details>
        `;
        rawResultsElement.style.display = 'block';
    }
}

/**
 * Display AI Image Creator cards in the UI
 * @param {object} results - The formatted search results
 */
function displayImageCreatorCards(results) {
    const cardsContainer = document.getElementById('ai-image-cards-container');
    if (!cardsContainer) return;
    
    // Clear previous results
    cardsContainer.innerHTML = '';
    
    // If no results, show a message
    if (!results.tools || results.tools.length === 0) {
        cardsContainer.innerHTML = '<p>No AI image creation tools found</p>';
        return;
    }
    
    // Create and append cards for each tool
    results.tools.forEach(tool => {
        const card = createImageCreatorCard(tool);
        cardsContainer.appendChild(card);
    });
}

/**
 * Create a card element for an AI Image Creator tool
 * @param {object} tool - The tool data
 * @returns {HTMLElement} - The card element
 */
function createImageCreatorCard(tool) {
    // Create card container
    const card = document.createElement('div');
    card.className = 'ai-image-card';
    card.dataset.objectId = tool.objectID;
    
    // Add header with tool name
    const header = document.createElement('div');
    header.className = 'card-header';
    header.textContent = tool.name;
    
    // Add logo/image
    const image = document.createElement('img');
    image.className = 'card-image';
    image.src = tool.image_url || tool.logo_url || '/placeholder-image.jpg';
    image.alt = `${tool.name} logo`;
    
    // Add description
    const description = document.createElement('div');
    description.className = 'card-description';
    description.textContent = tool.description;
    
    // Add "Try Tool" button
    const button = document.createElement('a');
    button.className = 'try-tool-button';
    button.href = tool.url;
    button.target = '_blank';
    button.textContent = 'Try Tool';
    
    // Add share button
    const shareButton = document.createElement('button');
    shareButton.className = 'share-button';
    shareButton.innerHTML = '<i class="share-icon"></i>';
    shareButton.addEventListener('click', (e) => {
        e.stopPropagation();
        shareTool(tool);
    });
    
    // Assemble card
    card.appendChild(header);
    card.appendChild(image);
    card.appendChild(description);
    
    const buttonContainer = document.createElement('div');
    buttonContainer.className = 'card-buttons';
    buttonContainer.appendChild(button);
    buttonContainer.appendChild(shareButton);
    card.appendChild(buttonContainer);
    
    // Add click event to show more details
    card.addEventListener('click', (event) => {
        // Don't trigger if clicking on the button or share button
        if (!event.target.closest('.try-tool-button') && !event.target.closest('.share-button')) {
            showToolDetails(tool.objectID);
        }
    });
    
    return card;
}

/**
 * Share a tool with others
 * @param {object} tool - The tool data
 */
function shareTool(tool) {
    // Implementation of sharing functionality
    // This could open a share dialog, copy a link to clipboard, etc.
    console.log('Sharing tool:', tool.name);
    
    // Example: Copy link to clipboard
    navigator.clipboard.writeText(tool.url)
        .then(() => {
            alert(`Link to ${tool.name} copied to clipboard!`);
        })
        .catch(err => {
            console.error('Failed to copy link:', err);
        });
}

/**
 * Show detailed information about a tool
 * @param {string} objectId - The Algolia objectID of the tool
 */
async function showToolDetails(objectId) {
    try {
        // Show loading state
        showLoadingState();
        
        // Get detailed tool information
        const toolDetails = await getToolDetails(objectId);
        
        // Display the tool details in a modal or expanded view
        displayToolDetailsModal(toolDetails);
        
    } catch (error) {
        console.error('Error showing tool details:', error);
        displayError(error.message);
    } finally {
        // Hide loading state
        hideLoadingState();
    }
}

/**
 * Display a modal with detailed tool information
 * @param {object} toolDetails - The detailed tool information
 */
function displayToolDetailsModal(toolDetails) {
    // Implementation of a modal or expanded view to show detailed tool information
    console.log('Displaying tool details:', toolDetails);
    
    // Create modal elements
    const modal = document.createElement('div');
    modal.className = 'tool-details-modal';
    
    const modalContent = document.createElement('div');
    modalContent.className = 'modal-content';
    
    // Add close button
    const closeButton = document.createElement('button');
    closeButton.className = 'close-button';
    closeButton.textContent = '×';
    closeButton.addEventListener('click', () => {
        document.body.removeChild(modal);
    });
    
    // Add content
    const header = document.createElement('h2');
    header.textContent = toolDetails.name;
    
    const image = document.createElement('img');
    image.src = toolDetails.image_url || toolDetails.logo_url || '/placeholder-image.jpg';
    image.alt = `${toolDetails.name} logo`;
    
    const description = document.createElement('p');
    description.textContent = toolDetails.description;
    
    const link = document.createElement('a');
    link.href = toolDetails.url || toolDetails.link || '#';
    link.target = '_blank';
    link.textContent = 'Visit Website';
    
    // Assemble modal
    modalContent.appendChild(closeButton);
    modalContent.appendChild(header);
    modalContent.appendChild(image);
    modalContent.appendChild(description);
    modalContent.appendChild(link);
    
    // Add additional details if available
    if (toolDetails.pricing_type) {
        const pricing = document.createElement('p');
        pricing.innerHTML = `<strong>Pricing:</strong> ${toolDetails.pricing_type}`;
        modalContent.appendChild(pricing);
    }
    
    if (toolDetails.categories && toolDetails.categories.length > 0) {
        const categories = document.createElement('p');
        categories.innerHTML = `<strong>Categories:</strong> ${toolDetails.categories.join(', ')}`;
        modalContent.appendChild(categories);
    }
    
    // Add raw JSON data in collapsible section
    const rawDataSection = document.createElement('details');
    rawDataSection.className = 'raw-data-section';
    
    const rawDataSummary = document.createElement('summary');
    rawDataSummary.textContent = 'View Complete Data';
    
    const rawDataPre = document.createElement('pre');
    rawDataPre.textContent = JSON.stringify(toolDetails, null, 2);
    
    rawDataSection.appendChild(rawDataSummary);
    rawDataSection.appendChild(rawDataPre);
    modalContent.appendChild(rawDataSection);
    
    modal.appendChild(modalContent);
    document.body.appendChild(modal);
}

/**
 * Show loading state in the UI
 */
function showLoadingState() {
    const loader = document.getElementById('loader');
    if (loader) {
        loader.style.display = 'block';
    }
}

/**
 * Hide loading state in the UI
 */
function hideLoadingState() {
    const loader = document.getElementById('loader');
    if (loader) {
        loader.style.display = 'none';
    }
}

/**
 * Display an error message in the UI
 * @param {string} message - The error message
 */
function displayError(message) {
    const errorElement = document.getElementById('error-message');
    if (errorElement) {
        errorElement.textContent = `Error: ${message}`;
        errorElement.style.display = 'block';
    }
}

// Example usage:
document.addEventListener('DOMContentLoaded', () => {
    // Get reference to search form
    const searchForm = document.getElementById('search-form');
    
    if (searchForm) {
        searchForm.addEventListener('submit', (event) => {
            event.preventDefault();
            
            const searchInput = document.getElementById('search-input');
            if (searchInput && searchInput.value.trim()) {
                searchAIImageTools(searchInput.value.trim());
            }
        });
    }
    
    // Optional: Run a default search on page load
    // searchAIImageTools('AI image generator');
}); 