import React from 'react';
import '../styles/Message.css';

const Message = ({ message, language }) => {
  const formatTime = (date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const texts = {
    en: {
      schemeDetails: 'Scheme Details:',
      eligibility: 'Eligibility:',
      benefits: 'Benefits:',
      documents: 'Required Documents:',
      suggestedSchemes: 'Suggested Schemes:',
      applyNow: 'Apply Now'
    },
    hi: {
      schemeDetails: 'योजना विवरण:',
      eligibility: 'पात्रता:',
      benefits: 'लाभ:',
      documents: 'आवश्यक दस्तावेज़:',
      suggestedSchemes: 'सुझाई गई योजनाएं:',
      applyNow: 'अभी आवेदन करें'
    }
  };

  const currentText = texts[language] || texts.en;

  // Render scheme details if available
  const renderSchemeDetails = () => {
    if (!message.scheme_details) return null;
    
    return (
      <div className="scheme-details">
        <h4>{currentText.schemeDetails}</h4>
        <p><strong>{message.scheme_details.scheme_name}</strong></p>
        <p>{message.scheme_details.description}</p>
        
        {message.scheme_details.eligibility_criteria && (
          <div className="eligibility">
            <p><strong>{currentText.eligibility}</strong></p>
            <ul>
              {message.scheme_details.eligibility_criteria.map((criteria, idx) => (
                <li key={idx}>{criteria.field}: {criteria.operator} {criteria.value}</li>
              ))}
            </ul>
          </div>
        )}
        
        {message.scheme_details.benefits && (
          <div className="benefits">
            <p><strong>{currentText.benefits}</strong></p>
            <ul>
              {message.scheme_details.benefits.map((benefit, idx) => (
                <li key={idx}>{benefit}</li>
              ))}
            </ul>
          </div>
        )}
        
        {message.scheme_details.documents_required && (
          <div className="documents">
            <p><strong>{currentText.documents}</strong></p>
            <ul>
              {message.scheme_details.documents_required.map((doc, idx) => (
                <li key={idx}>{doc}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  };

  // Render suggested schemes if available
  const renderSuggestedSchemes = () => {
    if (!message.suggested_schemes || message.suggested_schemes.length === 0) return null;
    
    return (
      <div className="suggested-schemes">
        <h4>{currentText.suggestedSchemes}</h4>
        <ul>
          {message.suggested_schemes.map((scheme, idx) => (
            <li key={idx}>
              <strong>{scheme.scheme_name}</strong>: {scheme.description}
            </li>
          ))}
        </ul>
      </div>
    );
  };

  return (
    <div className={`message message-${message.sender} ${message.isError ? 'message-error' : ''}`}>
      <div className="message-text">{message.text}</div>
      {renderSchemeDetails()}
      {renderSuggestedSchemes()}
      <div className="message-timestamp">{formatTime(message.timestamp)}</div>
    </div>
  );
};

export default Message;