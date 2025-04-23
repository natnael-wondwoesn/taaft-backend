/**
 * Tool Recommendations Component
 * 
 * This component renders recommended AI tools in the chat interface
 * when the user asks about tools or the LLM service determines
 * that tools would be helpful for the user's query.
 */

class ToolRecommendations {
    constructor() {
        this.toolsContainer = null;
        this.initStyles();
    }

    /**
     * Initialize the CSS styles for the component
     */
    initStyles() {
        // Add CSS styles to the document if not already present
        if (!document.getElementById('tool-recommendations-style')) {
            const style = document.createElement('style');
            style.id = 'tool-recommendations-style';
            style.textContent = `
                .tools-container {
                    margin-top: 12px;
                    border-top: 1px solid #e6e6e6;
                    padding-top: 12px;
                }
                
                .tools-heading {
                    font-size: 14px;
                    font-weight: 600;
                    color: #6665D9;
                    margin-bottom: 8px;
                }
                
                .tools-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                    gap: 12px;
                    margin-bottom: 12px;
                }
                
                .tool-card {
                    border: 1px solid #e0e0e0;
                    border-radius: 8px;
                    padding: 12px;
                    background-color: #f9f9fc;
                    transition: transform 0.2s, box-shadow 0.2s;
                }
                
                .tool-card:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }
                
                .tool-name {
                    font-weight: 600;
                    margin-bottom: 4px;
                    color: #333;
                }
                
                .tool-description {
                    font-size: 13px;
                    color: #555;
                    margin-bottom: 8px;
                    display: -webkit-box;
                    -webkit-line-clamp: 3;
                    -webkit-box-orient: vertical;
                    overflow: hidden;
                }
                
                .tool-meta {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    font-size: 12px;
                }
                
                .tool-categories {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 4px;
                }
                
                .tool-category {
                    background-color: #e9e9f9;
                    color: #6665D9;
                    padding: 2px 6px;
                    border-radius: 4px;
                    font-size: 11px;
                }
                
                .tool-pricing {
                    background-color: #f0f0f0;
                    color: #666;
                    padding: 2px 6px;
                    border-radius: 4px;
                    font-size: 11px;
                }
                
                .tool-link {
                    display: block;
                    text-align: right;
                    margin-top: 8px;
                    color: #6665D9;
                    font-size: 12px;
                    text-decoration: none;
                }
                
                .tool-link:hover {
                    text-decoration: underline;
                }
                
                .tools-more {
                    text-align: center;
                    margin-top: 8px;
                }
                
                .tools-more-link {
                    color: #6665D9;
                    font-size: 13px;
                    cursor: pointer;
                }
                
                .tools-more-link:hover {
                    text-decoration: underline;
                }
            `;
            document.head.appendChild(style);
        }
    }

    /**
     * Render tool recommendations in the specified container
     * 
     * @param {Array} tools - Array of tool objects to display
     * @param {HTMLElement} container - Container element to render tools in
     * @param {Object} options - Optional rendering options
     */
    render(tools, container, options = {}) {
        if (!tools || !tools.length) return;
        
        // Create the tools container if it doesn't exist
        if (!this.toolsContainer) {
            this.toolsContainer = document.createElement('div');
            this.toolsContainer.className = 'tools-container';
            container.appendChild(this.toolsContainer);
        } else {
            // Clear previous content
            this.toolsContainer.innerHTML = '';
        }
        
        // Add heading
        const heading = document.createElement('div');
        heading.className = 'tools-heading';
        heading.textContent = options.heading || 'Recommended AI Tools';
        this.toolsContainer.appendChild(heading);
        
        // Create grid for tools
        const toolsGrid = document.createElement('div');
        toolsGrid.className = 'tools-grid';
        this.toolsContainer.appendChild(toolsGrid);
        
        // Add each tool
        tools.forEach(tool => {
            const toolCard = this._createToolCard(tool);
            toolsGrid.appendChild(toolCard);
        });
        
        // Add "More tools" link if requested
        if (options.moreToolsLink) {
            const moreTools = document.createElement('div');
            moreTools.className = 'tools-more';
            
            const moreLink = document.createElement('span');
            moreLink.className = 'tools-more-link';
            moreLink.textContent = 'View more tools';
            moreLink.addEventListener('click', () => {
                if (typeof options.onMoreTools === 'function') {
                    options.onMoreTools();
                } else {
                    window.location.href = '/tools';
                }
            });
            
            moreTools.appendChild(moreLink);
            this.toolsContainer.appendChild(moreTools);
        }
    }
    
    /**
     * Create a card for a single tool
     * 
     * @param {Object} tool - Tool data
     * @returns {HTMLElement} Tool card element
     */
    _createToolCard(tool) {
        const card = document.createElement('div');
        card.className = 'tool-card';
        
        // Tool name
        const name = document.createElement('div');
        name.className = 'tool-name';
        name.textContent = tool.name;
        card.appendChild(name);
        
        // Tool description
        const description = document.createElement('div');
        description.className = 'tool-description';
        description.textContent = tool.description;
        card.appendChild(description);
        
        // Tool metadata (categories and pricing)
        const meta = document.createElement('div');
        meta.className = 'tool-meta';
        
        // Categories
        const categories = document.createElement('div');
        categories.className = 'tool-categories';
        
        if (tool.categories && tool.categories.length) {
            // Display up to 2 categories
            tool.categories.slice(0, 2).forEach(category => {
                const cat = document.createElement('span');
                cat.className = 'tool-category';
                cat.textContent = category;
                categories.appendChild(cat);
            });
        }
        
        meta.appendChild(categories);
        
        // Pricing
        if (tool.pricing_type) {
            const pricing = document.createElement('span');
            pricing.className = 'tool-pricing';
            pricing.textContent = tool.pricing_type;
            meta.appendChild(pricing);
        }
        
        card.appendChild(meta);
        
        // Link to tool
        if (tool.website) {
            const link = document.createElement('a');
            link.className = 'tool-link';
            link.href = tool.website;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            link.textContent = 'Visit tool →';
            card.appendChild(link);
        }
        
        return card;
    }
    
    /**
     * Clear the tool recommendations from the container
     */
    clear() {
        if (this.toolsContainer) {
            this.toolsContainer.remove();
            this.toolsContainer = null;
        }
    }
}

// Export the component
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ToolRecommendations;
} 